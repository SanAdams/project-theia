$procs = Get-WmiObject Win32_Process | Where-Object {
    ($_.Name -eq 'python.exe' -and $_.CommandLine -like '*uvicorn*') -or
    ($_.Name -eq 'node.exe'   -and ($_.CommandLine -like '*expo*' -or $_.CommandLine -like '*metro*'))
}

if ($procs) {
    $procs | ForEach-Object {
        Write-Host "Stopping $($_.Name) (PID $($_.ProcessId)): $($_.CommandLine.Substring(0, [Math]::Min(80, $_.CommandLine.Length)))"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host 'Theia stopped.'
} else {
    Write-Host 'No Theia processes found.'
}
