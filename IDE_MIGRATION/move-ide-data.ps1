param(
    [ValidateSet('Prepare','Worker','Status','VerifyVSCodeCopy')][string]$Mode = 'Status',
    [switch]$CloseSavedEditor
)
$ErrorActionPreference = 'Stop'
$base = 'D:\AIagent _openworld\IDE_MIGRATION'
$statePath = Join-Path $base 'status.json'
$taskName = 'Move-VSCode-Codex-Data-To-D-20261122'
$pairs = @(
    [pscustomobject]@{ Source='C:\Users\lenovo\.vscode'; Destination='D:\IDE\.vscode'; Backup='C:\Users\lenovo\.vscode.before-move-20261122' },
    [pscustomobject]@{ Source='C:\Users\lenovo\.codex'; Destination='D:\IDE\.codex'; Backup='C:\Users\lenovo\.codex.before-move-20261122' }
)
$editor = 'D:\c++\Microsoft VS Code\Code.exe'

function Set-State([string]$Stage, [string]$Message, $Detail = $null) {
    $value = [ordered]@{ Stage=$Stage; Message=$Message; Updated=(Get-Date).ToString('o'); Detail=$Detail }
    $temporary = "$statePath.new"
    $value | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $statePath -Force
}

function Assert-Paths {
    foreach ($p in $pairs) {
        if ([IO.Path]::GetFullPath($p.Source) -notin @('C:\Users\lenovo\.vscode','C:\Users\lenovo\.codex')) { throw 'Unexpected source.' }
        if ([IO.Path]::GetFullPath($p.Destination) -notin @('D:\IDE\.vscode','D:\IDE\.codex')) { throw 'Unexpected destination.' }
        if ($p.Backup -ne ($p.Source + '.before-move-20261122')) { throw 'Unexpected backup.' }
    }
    $ide = Get-Item -LiteralPath 'D:\IDE' -Force
    if ($ide.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'D:\IDE must be a physical directory.' }
}

function Get-BlockingProcesses {
    @(Get-Process | Where-Object {
        if ($_.Id -eq $PID) { return $false }
        if ($_.ProcessName -match '^(Code|Codex|codex-code-mode-host|ChatGPT)$') { return $true }
        try { $exe = $_.Path } catch { $exe = $null }
        $exe -and ($exe.StartsWith('C:\Users\lenovo\.codex\',[StringComparison]::OrdinalIgnoreCase) -or $exe.StartsWith('C:\Users\lenovo\.vscode\',[StringComparison]::OrdinalIgnoreCase))
    })
}

function Copy-Data($Pair) {
    Assert-Paths
    $src = Get-Item -LiteralPath $Pair.Source -Force
    if ($src.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Source is already a link: $($Pair.Source)" }
    if (-not (Test-Path -LiteralPath $Pair.Destination)) {
        New-Item -ItemType Directory -Path $Pair.Destination | Out-Null
    }
    $dst = Get-Item -LiteralPath $Pair.Destination -Force
    if ($dst.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Destination must not be a link.' }
    # Convert the profile's inherited rules to explicit rules. D:\ has different
    # inheritance; copying an inherited descriptor alone would grant other users access.
    $acl = Get-Acl -LiteralPath $Pair.Source
    $acl.SetAccessRuleProtection($true,$true)
    Set-Acl -LiteralPath $Pair.Destination -AclObject $acl
    # These exact destination folders are dedicated staging copies. Mirror only them.
    $log = Join-Path $base ((Split-Path $Pair.Source -Leaf) + '-copy.log')
    # /E /PURGE preserves destination root permissions; /MIR can overwrite them.
    & robocopy.exe $Pair.Source $Pair.Destination /E /PURGE /COPY:DATS /DCOPY:DAT /SJ /SL /R:1 /W:1 /MT:4 /NP /NFL /NDL "/LOG:$log" | Out-Null
    $code = $LASTEXITCODE
    # Robocopy can report exit 0 for an early root-security failure. Check its log too.
    if (Select-String -LiteralPath $log -Pattern '\bERROR\s+\d+\s+\(0x[0-9A-Fa-f]+\)' -Quiet) { $code = [math]::Max($code,8) }
    return $code
}

function Get-Inventory([string]$Root) {
    if (-not ('IdeMigrationHashV2' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Collections.Generic;
using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Threading.Tasks;
public static class IdeMigrationHashV2 {
    public static ConcurrentDictionary<string,string> Build(string root) {
        var result = new ConcurrentDictionary<string,string>(StringComparer.OrdinalIgnoreCase);
        var stack = new Stack<string>();
        var files = new List<KeyValuePair<string,FileInfo>>();
        stack.Push(root);
        while (stack.Count != 0) {
            foreach (FileSystemInfo entry in new DirectoryInfo(stack.Pop()).EnumerateFileSystemInfos()) {
                string relative = entry.FullName.Substring(root.Length).TrimStart('\\');
                if ((entry.Attributes & FileAttributes.ReparsePoint) != 0) {
                    result[relative] = "LINK";
                } else if ((entry.Attributes & FileAttributes.Directory) != 0) {
                    result[relative] = "DIR";
                    stack.Push(entry.FullName);
                } else {
                    files.Add(new KeyValuePair<string,FileInfo>(relative,(FileInfo)entry));
                }
            }
        }
        Parallel.ForEach(files,new ParallelOptions { MaxDegreeOfParallelism=4 }, item => {
            FileInfo file = item.Value;
            long expectedLength = file.Length;
            long expectedTime = file.LastWriteTimeUtc.Ticks;
            byte[] digest;
            using (var sha = SHA256.Create())
            using (var stream = new FileStream(file.FullName,FileMode.Open,FileAccess.Read,FileShare.Read,131072,FileOptions.SequentialScan)) {
                digest = sha.ComputeHash(stream);
            }
            file.Refresh();
            if (file.Length != expectedLength || file.LastWriteTimeUtc.Ticks != expectedTime)
                throw new IOException("File changed during verification: " + item.Key);
            result[item.Key] = "FILE|" + expectedLength + "|" + BitConverter.ToString(digest);
        });
        return result;
    }
}
'@
    }
    $result = [IdeMigrationHashV2]::Build($Root)
    foreach ($key in @($result.Keys)) {
        if ($result[$key] -eq 'LINK') {
            $link = Get-Item -LiteralPath (Join-Path $Root $key) -Force
            $result[$key] = 'LINK|' + $link.LinkType + '|' + ($link.Target -join '|')
        }
    }
    return ,$result
}

function Assert-Same($Original, $Copy) {
    if ($Original.Count -ne $Copy.Count) { throw "Inventory count mismatch: $($Original.Count) vs $($Copy.Count)." }
    foreach ($key in $Original.Keys) {
        if (-not $Copy.ContainsKey($key) -or $Original[$key] -cne $Copy[$key]) { throw "Verification mismatch: $key" }
    }
}

function Remove-VerifiedBackup($Pair) {
    Assert-Paths
    $backup = Get-Item -LiteralPath $Pair.Backup -Force
    $link = Get-Item -LiteralPath $Pair.Source -Force
    if (($backup.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $link.LinkType -ne 'Junction' -or $link.Target[0] -ne $Pair.Destination) { throw 'Unsafe cleanup paths.' }
    # Delete junction entries themselves; never recurse through their targets.
    $stack = [Collections.Generic.Stack[string]]::new()
    $folders = [Collections.Generic.List[string]]::new()
    $stack.Push($Pair.Backup)
    while ($stack.Count -gt 0) {
        $dir = $stack.Pop()
        if (-not ([IO.Path]::GetFullPath($dir).StartsWith($Pair.Backup + '\',[StringComparison]::OrdinalIgnoreCase)) -and $dir -ne $Pair.Backup) { throw 'Cleanup escaped backup.' }
        $folders.Add($dir)
        foreach ($item in Get-ChildItem -LiteralPath $dir -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                if ($item.PSIsContainer) { [IO.Directory]::Delete($item.FullName) } else { [IO.File]::Delete($item.FullName) }
            } elseif ($item.PSIsContainer) { $stack.Push($item.FullName) }
            else { Remove-Item -LiteralPath $item.FullName -Force }
        }
    }
    for ($index = $folders.Count - 1; $index -ge 0; $index--) { [IO.Directory]::Delete($folders[$index]) }
}

if ($Mode -eq 'VerifyVSCodeCopy') {
    $sourceFiles = Get-Inventory $pairs[0].Source
    Assert-Same $sourceFiles (Get-Inventory $pairs[0].Destination)
    Write-Output ('Verified VS Code copy with SHA-256: ' + $sourceFiles.Count + ' entries match.')
    exit
}

if ($Mode -eq 'Status') {
    if (Test-Path -LiteralPath $statePath) { Get-Content -LiteralPath $statePath }
    Get-Item -LiteralPath $pairs.Source -Force | Select-Object FullName,LinkType,Target
    exit
}

Assert-Paths
if ($Mode -eq 'Prepare') {
    foreach ($p in $pairs) {
        if (Test-Path -LiteralPath $p.Backup) { throw "An existing backup needs inspection: $($p.Backup)" }
        if ((Test-Path -LiteralPath $p.Destination) -and -not (Test-Path -LiteralPath $statePath)) { throw "Unmanaged destination already exists: $($p.Destination)" }
    }
    if (([IO.DriveInfo]::new('D:\')).AvailableFreeSpace -lt 6GB) { throw 'Insufficient free space on D.' }
    Set-State 'Preparing' 'Copying initial data. Original folders remain untouched.'
    $codes = @()
    foreach ($p in $pairs) {
        $code = Copy-Data $p
        $codes += [pscustomobject]@{ Source=$p.Source; CopyExitCode=$code }
        if ($code -ge 8) { Set-State 'PreparationNeedsAttention' 'Initial copy needs inspection. Originals have not been changed.' $codes; throw "Initial copy failed for $($p.Source). See copy log." }
    }
    # No programs are killed. A detached Task Scheduler action waits for a clean exit.
    $action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $PSCommandPath + '" -Mode Worker') -WorkingDirectory $base
    $principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Trigger $trigger -Description 'One-time verified migration of .vscode and .codex to D:\IDE, after VS Code exits.' -Force -ErrorAction Stop | Out-Null
    Set-State 'WaitingForAppsToClose' 'Save work and close all VS Code/Codex windows. Migration will then run automatically and reopen VS Code.' $codes
    Start-ScheduledTask -TaskName $taskName
    Get-Content -LiteralPath $statePath
    exit
}

# Worker runs outside the editor process tree, including after the editor exits.
$mutex = [Threading.Mutex]::new($false,'Local\MoveVSCodeCodexData20261122')
if (-not $mutex.WaitOne(0)) { exit }
$swapped = [Collections.Generic.List[object]]::new()
$cutoverStarted = $false
$cleanupStarted = $false
try {
    $freeBefore = ([IO.DriveInfo]::new('C:\')).AvailableFreeSpace
    if ($CloseSavedEditor) {
        # Enabled only after the user confirms that their edits have been saved.
        Set-State 'RestartingEditor' 'User confirmed edits are saved. Closing VS Code temporarily to finish the migration.' @{ WorkerPID=$PID }
        Start-Sleep -Seconds 10
        foreach ($proc in @(Get-Process -Name Code,codex,codex-code-mode-host -ErrorAction SilentlyContinue)) {
            try { $exePath = $proc.Path } catch { $exePath = $null }
            if ($exePath -and ($exePath -eq $editor -or $exePath.StartsWith('C:\Users\lenovo\.vscode\',[StringComparison]::OrdinalIgnoreCase) -or $exePath.StartsWith('C:\Users\lenovo\.codex\',[StringComparison]::OrdinalIgnoreCase))) {
                Stop-Process -InputObject $proc -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Set-State 'WaitingForAppsToClose' 'Background worker is ready. Save work and close all VS Code/Codex windows to complete migration.' @{ WorkerPID=$PID }
    :MigrationLoop while ($true) {
        while (@(Get-BlockingProcesses).Count -gt 0) { Start-Sleep -Seconds 3 }
        Start-Sleep -Seconds 8
        if (@(Get-BlockingProcesses).Count -gt 0) { continue }
        Set-State 'FinalCopy' 'Applications closed. Refreshing both copies.'
        foreach ($p in $pairs) {
            $code = Copy-Data $p
            if ($code -ge 8) { throw "Final copy failed for $($p.Source), robocopy exit $code. See copy log." }
        }
        Set-State 'Verifying' 'Comparing every file with parallel SHA-256 before changing original folders.'
        $inventories = @{}
        try {
            foreach ($p in $pairs) {
                $inventories[$p.Source] = Get-Inventory $p.Source
                $destinationInventory = Get-Inventory $p.Destination
                if (@(Get-BlockingProcesses).Count -gt 0) {
                    Set-State 'WaitingForAppsToClose' 'The editor reopened during verification. Originals are unchanged; waiting to verify again.'
                    continue MigrationLoop
                }
                Assert-Same $inventories[$p.Source] $destinationInventory
            }
        } catch {
            if (@(Get-BlockingProcesses).Count -gt 0) {
                Set-State 'WaitingForAppsToClose' 'The editor reopened during verification. Originals are unchanged; waiting to verify again.'
                continue MigrationLoop
            }
            throw
        }
        if (@(Get-BlockingProcesses).Count -gt 0) {
            Set-State 'WaitingForAppsToClose' 'An application reopened. Waiting again before switching paths.'
            continue
        }
        break
    }
    $cutoverStarted = $true
    Set-State 'Switching' 'Creating compatibility junctions at the original paths.'
    foreach ($p in $pairs) {
        Assert-Paths
        if (Test-Path -LiteralPath $p.Backup) { throw 'Backup already exists.' }
        Move-Item -LiteralPath $p.Source -Destination $p.Backup
        $swapped.Add($p)
        New-Item -ItemType Junction -Path $p.Source -Target $p.Destination | Out-Null
        $link = Get-Item -LiteralPath $p.Source -Force
        if ($link.LinkType -ne 'Junction' -or $link.Target[0] -ne $p.Destination) { throw 'Junction verification failed.' }
        $probeName = '.migration-probe-' + [Guid]::NewGuid().ToString('N')
        $probe = Join-Path $p.Source $probeName
        [IO.File]::WriteAllText($probe, 'junction-test')
        try {
            if ([IO.File]::ReadAllText((Join-Path $p.Destination $probeName)) -ne 'junction-test') { throw 'Write-through verification failed.' }
        } finally { [IO.File]::Delete($probe) }
    }
    foreach ($p in $pairs) { Assert-Same $inventories[$p.Source] (Get-Inventory $p.Backup) }
    $cleanupStarted = $true
    Set-State 'CleaningVerifiedOriginals' 'Both junctions passed verification. Removing verified original data from C.'
    foreach ($p in $pairs) { Remove-VerifiedBackup $p }
    $freed = ([IO.DriveInfo]::new('C:\')).AvailableFreeSpace - $freeBefore
    Set-State 'Complete' 'Both folders now reside on D:\IDE. Original paths are working junctions. VS Code is reopening.' @{ FreedBytes=$freed; Mappings=$pairs | Select-Object Source,Destination }
    $report = Join-Path $base 'KET_QUA.txt'
    @(
        'DA HOAN TAT CHUYEN DU LIEU SANG O D.',
        '',
        'C:\Users\lenovo\.vscode -> D:\IDE\.vscode',
        'C:\Users\lenovo\.codex  -> D:\IDE\.codex',
        '',
        ('Dung luong trong o C tang: ' + [math]::Round($freed / 1GB,2) + ' GB.'),
        'Ban goc da duoc kiem tra SHA-256 va xoa khoi o C.',
        'Hai thu muc cu tren C chi la lien ket sang D. Hay giu cac lien ket nay.',
        '',
        ('Thoi gian hoan tat: ' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))
    ) | Set-Content -LiteralPath $report -Encoding UTF8
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $editor) { Start-Process -FilePath $editor -ArgumentList '"D:\AIagent _openworld"' -WindowStyle Normal }
    if ($CloseSavedEditor) { Start-Process -FilePath "$env:SystemRoot\System32\notepad.exe" -ArgumentList ('"' + $report + '"') -WindowStyle Normal }
} catch {
    $errorText = $_.Exception.Message
    if ($cutoverStarted -and -not $cleanupStarted) {
        for ($index=$swapped.Count-1; $index -ge 0; $index--) {
            $p = $swapped[$index]
            try {
                if (Test-Path -LiteralPath $p.Source) {
                    $link = Get-Item -LiteralPath $p.Source -Force
                    if ($link.LinkType -ne 'Junction' -or $link.Target[0] -ne $p.Destination) { throw 'Unexpected item at rollback path.' }
                    [IO.Directory]::Delete($p.Source)
                }
                Move-Item -LiteralPath $p.Backup -Destination $p.Source
            } catch { $errorText += ' Rollback: ' + $_.Exception.Message }
        }
    }
    Set-State 'NeedsAttention' $errorText @{ CleanupStarted=$cleanupStarted }
    # Prevent repeating a failed operation automatically at login.
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
