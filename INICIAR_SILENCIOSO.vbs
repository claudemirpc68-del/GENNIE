Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\FAMÍLIA\Desktop\GENNIE_BOT"
WshShell.Run "cmd.exe /c python gennie.py", 0, False
