Set ws  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' 读取 .env 文件中的环境变量
envFile = scriptDir & "\.env"
If fso.FileExists(envFile) Then
    Set f = fso.OpenTextFile(envFile, 1)
    Do While Not f.AtEndOfStream
        line = Trim(f.ReadLine())
        If Len(line) > 0 And Left(line, 1) <> "#" Then
            eqPos = InStr(line, "=")
            If eqPos > 0 Then
                key = Trim(Left(line, eqPos - 1))
                val = Trim(Mid(line, eqPos + 1))
                ws.Environment("PROCESS")(key) = val
            End If
        End If
    Loop
    f.Close
End If

ws.Run "python """ & scriptDir & "\app.py""", 0, False
