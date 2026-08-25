' Sobe o painel sem abrir janela de console.
' Coloque um atalho deste arquivo em shell:startup para iniciar com o Windows.
Set fso = CreateObject("Scripting.FileSystemObject")
pasta = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = pasta
If fso.FileExists(pasta & "\.venv\Scripts\pythonw.exe") Then
  python = """" & pasta & "\.venv\Scripts\pythonw.exe"""
Else
  python = "pythonw"
End If
shell.Run python & " -m src.scripts.painel", 0, False
