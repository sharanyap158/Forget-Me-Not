
        $wshell = New-Object -ComObject WScript.Shell
        $wshell.Popup("It's time for dinner!", 10, "Dinner", 0x1)
        exit
        