' Arsenal_Candidatures - lanceur
' Double-clic : traite les offres en attente puis ouvre le tableau de bord.

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Detection de python.exe
python = "python.exe"
defaultPath = "C:\Users\Gstar\AppData\Local\Programs\Python\Python312\python.exe"
If fso.FileExists(defaultPath) Then
    python = defaultPath
End If

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = scriptDir

' Lance le traitement dans une fenetre visible et attend la fin
WshShell.Run """" & python & """ """ & scriptDir & "\run_candidatures.py""", 1, True

' Ouvre le tableau de bord
dashboard = scriptDir & "\_logs\tableau_de_bord.md"
If fso.FileExists(dashboard) Then
    WshShell.Run "notepad """ & dashboard & """", 1, False
End If
