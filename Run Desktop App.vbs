Option Explicit

Dim shell, fileSystem, projectDir, launcher
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

projectDir = fileSystem.GetParentFolderName(WScript.ScriptFullName)
launcher = """" & projectDir & "\Run Desktop App.bat"""

' Window style 0 keeps the bootstrap console hidden.
shell.Run launcher, 0, False
