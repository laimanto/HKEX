# HKEX Dashboard — Monthly Update & Publish
# Runs on the 1st of each month via Windows Task Scheduler.
# Fetches latest data, rebuilds the dashboard, and pushes to GitHub.

$python = "C:\Python314\python.exe"
$git    = "C:\Users\laima\AppData\Local\GitHubDesktop\app-3.5.12\resources\app\git\cmd\git.exe"
$proj   = "D:\Backup D\Weekly\USB drive\Invest\AI invest\388"
$log    = "$proj\update_log.txt"

Set-Location $proj
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  START monthly update" | Out-File $log -Append -Encoding utf8

& $python fetch_dashboard_data.py | Out-File $log -Append -Encoding utf8
& $python build_dashboard.py      | Out-File $log -Append -Encoding utf8

& $git add -A
$staged = & $git status --porcelain
if ($staged) {
    & $git commit -m "Monthly dashboard update $(Get-Date -Format 'yyyy-MM-dd')"
    & $git push origin main
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  Published to GitHub" | Out-File $log -Append -Encoding utf8
} else {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  No changes to publish" | Out-File $log -Append -Encoding utf8
}

"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  DONE" | Out-File $log -Append -Encoding utf8
