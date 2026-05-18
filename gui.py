#!/usr/bin/env python3
"""Arsenal Candidatures — interface graphique.

Tableau de bord unique : voir les offres scrapées, marquer celles qui
intéressent, générer le CV + la lettre, suivre les candidatures envoyées.

Deux axes indépendants par offre :
  - intérêt    : marqué par l'utilisateur (intéressé / ignoré)
  - avancement : état du dossier (CV généré / envoyé)
Le statut affiché est déduit des deux.

Lancement : double-clic sur start_gui.vbs (ou `python gui.py`).
"""
import os
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts import (offres_store, scraper, generate, ingest, suivi,  # noqa: E402
                     archivage)
from scripts.offres_store import LIBELLES, STATUTS, statut_derive    # noqa: E402
from scripts.logger_setup import get_logger                         # noqa: E402

log = get_logger()

COULEURS = {
    "nouveau": "#FFFFFF",
    "interesse": "#D6EAF8",
    "cv_genere": "#D5F5E3",
    "envoye": "#ABEBC6",
    "ignore": "#E5E7E9",
}


def _fmt_horodatage(iso: str) -> str:
    """Convertit un horodatage stocké en JJ/MM/AA HH:MM.

    Les anciennes valeurs sans heure restent acceptées (affichées sans heure).
    """
    if not iso:
        return ""
    for entree, sortie in (("%Y-%m-%d %H:%M", "%d/%m/%y %H:%M"),
                           ("%Y-%m-%d", "%d/%m/%y")):
        try:
            return datetime.strptime(iso, entree).strftime(sortie)
        except ValueError:
            continue
    return ""


def _horodatage_brut(offre: dict, statut: str) -> str:
    """Horodatage ISO de l'événement correspondant au statut, '' si inconnu.

    Le format reste triable lexicalement (AAAA-MM-JJ [HH:MM]) : la fonction sert
    au tri du tableau et, une fois passée dans _fmt_horodatage, à l'affichage.

    - CV généré / envoyé : le champ enregistré s'il a l'heure, sinon la date de
      modification du PDF (vraie date ET heure de génération), ce qui rend
      l'heure visible même pour les CV produits avant cette fonctionnalité.
    - Intéressé / ignoré : le champ `interet_le` du clic ; à défaut (offre
      marquée avant cette fonctionnalité), la date d'ajout de l'offre, qui en
      donne un repère approximatif, sans heure.
    """
    if statut == "envoye" and offre.get("envoye_le"):
        return offre["envoye_le"]
    if statut in ("cv_genere", "envoye"):
        iso = offre.get("cv_genere_le")
        if iso and len(iso) > 10:             # "%Y-%m-%d" fait 10 caractères
            return iso
        pdf = offre.get("cv_pdf")
        if pdf and os.path.exists(pdf):
            try:
                return datetime.fromtimestamp(
                    os.path.getmtime(pdf)).strftime("%Y-%m-%d %H:%M")
            except OSError:
                pass
        return iso or ""
    if statut in ("interesse", "ignore"):
        return offre.get("interet_le") or offre.get("date_ajout") or ""
    return ""


def _libelle_statut(offre: dict, statut: str) -> str:
    """Libellé du statut, complété de la date et l'heure de l'événement."""
    libelle = LIBELLES.get(statut, statut)
    horodatage = _fmt_horodatage(_horodatage_brut(offre, statut))
    if horodatage:
        libelle = f"{libelle} ({horodatage})"
    return libelle


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.occupe = False
        self.offres_affichees = []
        self.tri = ("score", True)          # (colonne, ordre décroissant)
        root.title("Arsenal Candidatures")
        root.geometry("1120x660")
        root.minsize(900, 500)
        self._construire()
        self.rafraichir()

    # ------------------------------------------------------------------ UI
    def _construire(self) -> None:
        haut = ttk.Frame(self.root, padding=8)
        haut.pack(fill="x")
        self.btn_ft = ttk.Button(haut, text="Scraper France Travail",
                                 command=lambda: self._lancer_scraper("francetravail"))
        self.btn_ft.pack(side="left")
        self.btn_agro = ttk.Button(haut, text="Scraper agro (lagrorecrute)",
                                   command=lambda: self._lancer_scraper("lagrorecrute"))
        self.btn_agro.pack(side="left", padx=4)
        ttk.Button(haut, text="Rafraîchir", command=self.rafraichir).pack(side="left")
        ttk.Label(haut, text="Filtre :").pack(side="left", padx=(16, 2))
        self.filtre = ttk.Combobox(haut, state="readonly", width=13,
                                   values=["Tous"] + [LIBELLES[s] for s in STATUTS])
        self.filtre.set("Tous")
        self.filtre.pack(side="left")
        self.filtre.bind("<<ComboboxSelected>>", lambda e: self.rafraichir())
        self.lbl_compte = ttk.Label(haut, text="")
        self.lbl_compte.pack(side="right")

        cadre = ttk.Frame(self.root)
        cadre.pack(fill="both", expand=True, padx=8)
        self.cols = ("statut", "titre", "entreprise", "lieu", "contrat", "score")
        largeurs = {"statut": 195, "titre": 285, "entreprise": 180,
                    "lieu": 150, "contrat": 140, "score": 55}
        self.entetes = {"statut": "Statut", "titre": "Titre",
                        "entreprise": "Entreprise", "lieu": "Lieu",
                        "contrat": "Contrat", "score": "Score"}
        self.tree = ttk.Treeview(cadre, columns=self.cols, show="headings",
                                 selectmode="extended")
        for c in self.cols:
            self.tree.heading(c, text=self.entetes[c],
                              command=lambda col=c: self._trier(col))
            self.tree.column(c, width=largeurs[c],
                             anchor="center" if c == "score" else "w")
        sb = ttk.Scrollbar(cadre, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._sur_selection())
        for statut, couleur in COULEURS.items():
            self.tree.tag_configure(statut, background=couleur)

        bas = ttk.Frame(self.root, padding=8)
        bas.pack(fill="x")
        for i in range(8):
            bas.columnconfigure(i, weight=1)
        self.lbl_sel = ttk.Label(bas, text="Aucune offre sélectionnée.",
                                 font=("Segoe UI", 9, "bold"))
        self.lbl_sel.grid(row=0, column=0, columnspan=8, sticky="w", pady=(0, 6))

        self.boutons = {}
        actions = [
            ("interesse", "Intéressé", lambda: self._definir_interet("interesse")),
            ("ignore", "Ignorer", lambda: self._definir_interet("ignore")),
            ("generer", "Générer CV + lettre", self._generer_selection),
            ("envoye", "Marquer envoyé", lambda: self._definir_avancement("envoye")),
            ("url", "Ouvrir l'offre", lambda: self._ouvrir("url")),
            ("cv_pdf", "Ouvrir CV", lambda: self._ouvrir("cv_pdf")),
            ("lettre_pdf", "Ouvrir lettre PDF", lambda: self._ouvrir("lettre_pdf")),
            ("lettre_txt", "Ouvrir lettre texte", lambda: self._ouvrir("lettre_txt")),
        ]
        for i, (cle, texte, commande) in enumerate(actions):
            bouton = ttk.Button(bas, text=texte, command=commande, state="disabled")
            bouton.grid(row=1, column=i, padx=2, sticky="ew")
            self.boutons[cle] = bouton

        self.btn_lot = ttk.Button(bas, text="Générer pour les « Intéressé » sans CV",
                                  command=self._generer_interesses)
        self.btn_lot.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

        ttk.Label(bas, text="Note :").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.note = ttk.Entry(bas)
        self.note.grid(row=3, column=1, columnspan=5, sticky="ew", pady=(8, 0))
        self.btn_note = ttk.Button(bas, text="Enregistrer la note",
                                   command=self._enregistrer_note, state="disabled")
        self.btn_note.grid(row=3, column=6, columnspan=2, sticky="ew", pady=(8, 0))

        self.barre = ttk.Label(self.root, text="Prêt.", relief="sunken",
                               anchor="w", padding=4)
        self.barre.pack(fill="x", side="bottom")

    # -------------------------------------------------------------- données
    def rafraichir(self) -> None:
        data = offres_store.charger()
        toutes = data.get("offres", [])
        libelle = self.filtre.get()
        statut_filtre = next((s for s in STATUTS if LIBELLES[s] == libelle), None)
        self.offres_affichees = [o for o in toutes
                                 if statut_filtre is None
                                 or statut_derive(o) == statut_filtre]
        col, reverse = self.tri
        self.offres_affichees.sort(key=lambda o: self._cle_tri(o, col),
                                   reverse=reverse)
        self._maj_entetes()

        self.tree.delete(*self.tree.get_children())
        for offre in self.offres_affichees:
            cle = offre.get("cle")
            if not cle:
                continue
            statut = statut_derive(offre)
            self.tree.insert("", "end", iid=cle, tags=(statut,), values=(
                _libelle_statut(offre, statut),
                offre.get("titre", ""),
                offre.get("entreprise", ""),
                offre.get("lieu", ""),
                offre.get("contrat", ""),
                offre.get("score", 0),
            ))

        counts = {s: 0 for s in STATUTS}
        for o in toutes:
            counts[statut_derive(o)] += 1
        self.lbl_compte.config(text=f"{len(toutes)} offres   |   " + "   ".join(
            f"{LIBELLES[s]}: {counts[s]}" for s in STATUTS))
        self._sur_selection()

    # ------------------------------------------------------------------ tri
    def _cle_tri(self, offre: dict, col: str):
        """Clé de tri d'une offre pour la colonne demandée."""
        if col == "score":
            return offre.get("score", 0) or 0
        if col == "statut":
            # Tri par date et heure de l'événement (marqué, CV généré, envoyé).
            return _horodatage_brut(offre, statut_derive(offre))
        return str(offre.get(col, "") or "").lower()

    def _trier(self, col: str) -> None:
        """Clic sur un en-tête : trie par cette colonne, inverse si déjà active."""
        actuel, reverse = self.tri
        if col == actuel:
            reverse = not reverse
        else:
            # Premier clic : score et date du plus récent/haut au plus bas.
            reverse = col in ("score", "statut")
        self.tri = (col, reverse)
        self.rafraichir()

    def _maj_entetes(self) -> None:
        """Affiche une flèche sur l'en-tête de la colonne de tri active."""
        col_actif, reverse = self.tri
        for c in self.cols:
            texte = self.entetes[c]
            if c == col_actif:
                texte += "  ▼" if reverse else "  ▲"
            self.tree.heading(c, text=texte)

    def _offre_par_cle(self, cle: str):
        for offre in offres_store.charger().get("offres", []):
            if offre.get("cle") == cle:
                return offre
        return None

    def _selection(self) -> list:
        return list(self.tree.selection())

    # ------------------------------------------------------------- sélection
    def _sur_selection(self) -> None:
        sel = self._selection()
        multi = len(sel) >= 1
        unique = len(sel) == 1
        for cle in ("interesse", "ignore", "generer", "envoye"):
            self.boutons[cle].config(
                state="normal" if multi and not self.occupe else "disabled")
        offre = self._offre_par_cle(sel[0]) if unique else None
        for champ in ("url", "cv_pdf", "lettre_pdf", "lettre_txt"):
            ok = bool(offre and offre.get(champ))
            self.boutons[champ].config(state="normal" if ok else "disabled")
        self.btn_note.config(state="normal" if unique else "disabled")
        self.note.delete(0, "end")
        if unique and offre:
            self.note.insert(0, offre.get("notes", ""))
            self.lbl_sel.config(text=f"Sélection : {offre.get('titre', '')}")
        elif multi:
            self.lbl_sel.config(text=f"{len(sel)} offres sélectionnées.")
        else:
            self.lbl_sel.config(text="Aucune offre sélectionnée.")

    # --------------------------------------------------------------- actions
    def _definir_interet(self, valeur: str) -> None:
        horodatage = datetime.now().strftime("%Y-%m-%d %H:%M")
        archives = restaures = 0
        for cle in self._selection():
            offre = self._offre_par_cle(cle)
            champs = {"interet": valeur, "interet_le": horodatage}
            try:
                if (offre and valeur == "ignore" and offre.get("cv_pdf")
                        and not offre.get("archive")):
                    champs.update(archivage.archiver(offre))
                    archives += 1
                elif offre and valeur == "interesse" and offre.get("archive"):
                    champs.update(archivage.restaurer(offre))
                    restaures += 1
            except OSError as e:
                log.error("Archivage/restauration impossible (%s) : %s", cle, e)
                messagebox.showerror(
                    "Déplacement impossible",
                    "Impossible de déplacer les fichiers. Le CV ou la lettre "
                    f"est peut-être ouvert dans un autre programme.\n\n{e}")
            offres_store.maj_offre(cle, **champs)
        self.rafraichir()
        message = f"Intérêt mis à jour : {LIBELLES.get(valeur, valeur)}."
        if archives:
            message += f" {archives} CV archivé(s)."
        if restaures:
            message += f" {restaures} CV restauré(s)."
        self.barre.config(text=message)

    def _definir_avancement(self, valeur: str) -> None:
        champs = {"avancement": valeur}
        if valeur == "envoye":
            champs["envoye_le"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        for cle in self._selection():
            offres_store.maj_offre(cle, **champs)
        self.rafraichir()
        self.barre.config(text="Avancement mis à jour.")

    def _ouvrir(self, champ: str) -> None:
        sel = self._selection()
        if not sel:
            return
        offre = self._offre_par_cle(sel[0])
        valeur = offre.get(champ) if offre else None
        if not valeur:
            return
        try:
            if champ == "url":
                webbrowser.open(valeur)
            else:
                os.startfile(valeur)        # noqa: S606 (Windows)
        except OSError as e:
            messagebox.showerror("Ouverture impossible", str(e))

    def _enregistrer_note(self) -> None:
        sel = self._selection()
        if len(sel) == 1:
            offres_store.maj_offre(sel[0], notes=self.note.get())
            self.barre.config(text="Note enregistrée.")

    # ------------------------------------------------------- tâches de fond
    def _set_occupe(self, occupe: bool) -> None:
        self.occupe = occupe
        etat = "disabled" if occupe else "normal"
        for bouton in (self.btn_ft, self.btn_agro, self.btn_lot):
            bouton.config(state=etat)
        self._sur_selection()

    def _async(self, message: str) -> None:
        self.root.after(0, lambda: self.barre.config(text=message))

    def _lancer_scraper(self, source: str) -> None:
        if self.occupe:
            return
        self._set_occupe(True)
        self.barre.config(text=f"Scraping ({source}) en cours...")

        def tache():
            try:
                res = scraper.scraper(source)
                self._async(f"Scraping terminé : {res['total']} offre(s).")
            except Exception as e:                    # noqa: BLE001
                log.error("Scraper échoué : %s", e)
                self._async(f"Échec du scraping : {e}")
            self.root.after(0, self._fin_tache)

        threading.Thread(target=tache, daemon=True).start()

    def _generer_selection(self) -> None:
        sel = self._selection()
        if not sel:
            return
        deja = [c for c in sel
                if (self._offre_par_cle(c) or {}).get("cv_pdf")]
        a_generer = [c for c in sel if c not in deja]
        if deja:
            if len(deja) == len(sel):
                question = ("Le CV de cette offre a déjà été généré et l'offre "
                            "n'a pas changé. Le régénérer quand même ?")
            else:
                question = (f"{len(deja)} offre(s) sur {len(sel)} ont déjà un CV "
                            "généré.\n\nOui : tout régénérer.\nNon : ne générer "
                            "que les offres sans CV.")
            reponse = messagebox.askyesnocancel("Génération", question)
            if reponse is None:
                return
            if reponse:
                a_generer = sel
        if not a_generer:
            self.barre.config(text="Rien à générer : CV déjà existant(s).")
            return
        self._lancer_generation(a_generer)

    def _generer_interesses(self) -> None:
        cles = [o["cle"] for o in offres_store.charger().get("offres", [])
                if o.get("interet") == "interesse" and not o.get("cv_pdf")]
        if not cles:
            messagebox.showinfo("Génération en lot",
                                "Aucune offre « Intéressé » sans CV à générer.")
            return
        if messagebox.askyesno("Génération en lot",
                               f"Générer le CV et la lettre pour {len(cles)} "
                               f"offre(s) ? Cela peut prendre quelques minutes."):
            self._lancer_generation(cles)

    def _lancer_generation(self, cles: list) -> None:
        if self.occupe or not cles:
            return
        self._set_occupe(True)

        def tache():
            total = len(cles)
            for i, cle in enumerate(cles, 1):
                offre = self._offre_par_cle(cle)
                if not offre:
                    continue
                self._async(f"Génération {i}/{total} : "
                            f"{offre.get('titre', '')[:55]}...")
                try:
                    self._generer_une(cle, offre)
                except Exception as e:                # noqa: BLE001
                    log.error("Génération échouée (%s) : %s", cle, e)
                    self._async(f"Échec sur une offre : {e}")
            suivi.generer_tableau_de_bord()
            self._async(f"Génération terminée ({total} offre(s)).")
            self.root.after(0, self._fin_tache)

        threading.Thread(target=tache, daemon=True).start()

    def _generer_une(self, cle: str, offre: dict) -> None:
        texte = scraper.charger_texte_offre(offre.get("url", ""))
        repli = (f"{offre.get('titre', '')} chez "
                 f"{offre.get('entreprise') or 'entreprise non précisée'}, "
                 f"{offre.get('lieu', '')}, contrat {offre.get('contrat', '')}.")
        offre_gen = {
            "titre_offre": offre.get("titre", ""),
            "entreprise": offre.get("entreprise", ""),
            "lieu": offre.get("lieu", ""),
            "type_contrat": offre.get("contrat", ""),
            "url": offre.get("url", ""),
            "description_structuree": "",
            "texte_page": texte or repli,
        }
        oid, dossier = ingest.creer_dossier_offre(offre_gen)
        resultat = generate.generer(offre_gen, oid, dossier)
        suivi.ajouter(oid, offre_gen, resultat)
        offres_store.maj_offre(
            cle, avancement="cv_genere",
            cv_genere_le=datetime.now().strftime("%Y-%m-%d %H:%M"),
            cv_pdf=resultat.get("cv_pdf"),
            lettre_pdf=resultat.get("lettre_pdf"),
            lettre_txt=resultat.get("lettre_txt"))

    def _fin_tache(self) -> None:
        self._set_occupe(False)
        self.rafraichir()


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
