wsl -d kali-linux -- systemctl --user stop cairn-workbench.service
wsl -d kali-linux -- pkill -f '^cairn-workbench-host infinity$'
