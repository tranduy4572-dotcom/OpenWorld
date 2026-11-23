param([ValidateSet('Preflight','Run')][string]$Mode = 'Preflight')
$ErrorActionPreference = 'Stop'
$base = 'D:\AIagent _openworld\IDE_MIGRATION'
$statusPath = Join-Path $base $(if ($Mode -eq 'Preflight') { 'preflight-v4.json' } else { 'status.json' })
$taskName = 'Move-VSCode-Codex-Data-To-D-20261122'
$editor = 'D:\c++\Microsoft VS Code\Code.exe'
$pairs = @(
    @{Source='C:\Users\lenovo\.vscode';Target='D:\IDE\.vscode';Backup='C:\Users\lenovo\.vscode.before-move-20261122'},
    @{Source='C:\Users\lenovo\.codex';Target='D:\IDE\.codex';Backup='C:\Users\lenovo\.codex.before-move-20261122'}
)
function State([string]$stage,[string]$message,$detail=$null) {
    @{Stage=$stage;Message=$message;Updated=(Get-Date).ToString('o');Detail=$detail} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$statusPath.new" -Encoding UTF8
    Move-Item -LiteralPath "$statusPath.new" -Destination $statusPath -Force
}
function Assert-Physical([string]$path) {
    $item=Get-Item -LiteralPath $path -Force
    if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Expected physical directory: $path" }
}
function Validate-Paths {
    Assert-Physical 'D:\IDE'
    foreach ($p in $pairs) {
        if ($p.Source -notin @('C:\Users\lenovo\.vscode','C:\Users\lenovo\.codex') -or $p.Target -notin @('D:\IDE\.vscode','D:\IDE\.codex') -or $p.Backup -ne ($p.Source+'.before-move-20261122')) { throw 'Unexpected migration paths.' }
        Assert-Physical $p.Target
        $acl=[IO.Directory]::GetAccessControl($p.Target,[Security.AccessControl.AccessControlSections]::Access)
        if (-not $acl.AreAccessRulesProtected) { throw "Destination permissions need inspection: $($p.Target)" }
    }
}
function Blockers {
    @(Get-Process | Where-Object {
        if ($_.Id -eq $PID) { return $false }
        if ($_.ProcessName -match '^(Code|codex|codex-code-mode-host)$') { return $true }
        try { $path=$_.Path } catch { $path=$null }
        $path -and ($path.StartsWith('C:\Users\lenovo\.codex\',[StringComparison]::OrdinalIgnoreCase) -or $path.StartsWith('C:\Users\lenovo\.vscode\',[StringComparison]::OrdinalIgnoreCase))
    })
}
function Copy-Folders {
    Validate-Paths
    foreach ($p in $pairs) {
        Assert-Physical $p.Source
        $log=Join-Path $base ((Split-Path $p.Source -Leaf)+'-copy-v3.log')
        # Root permissions are already protected and verified; do not copy audit metadata.
        & robocopy.exe $p.Source $p.Target /E /PURGE /COPY:DAT /DCOPY:DAT /SJ /SL /R:1 /W:1 /MT:4 /NP /NFL /NDL "/LOG:$log" | Out-Null
        $code=$LASTEXITCODE
        if ($code -ge 8 -or (Select-String -LiteralPath $log -Pattern '\bERROR\s+\d+\s+\(0x[0-9A-Fa-f]+\)' -Quiet)) { throw "Copy failed: $($p.Source). See $log" }
        if ($Mode -eq 'Run' -and $p.Source -eq 'C:\Users\lenovo\.codex') {
            # Memory-mapped SQLite sidecars can change without a useful timestamp.
            # Always refresh their bytes once all database writers have exited.
            foreach ($dbRoot in @($p.Source,(Join-Path $p.Source 'sqlite'))) {
                if (Test-Path -LiteralPath $dbRoot) {
                    foreach ($db in Get-ChildItem -LiteralPath $dbRoot -File -Force | Where-Object Name -Match '\.(sqlite|db)(-(wal|shm))?$') {
                        $relative=$db.FullName.Substring($p.Source.Length).TrimStart('\')
                        [IO.File]::Copy($db.FullName,(Join-Path $p.Target $relative),$true)
                    }
                }
            }
        }
    }
}
Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Collections.Generic;
using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Threading.Tasks;
public static class IdeMoveHashV4 {
 static ConcurrentDictionary<string,string> cache=new ConcurrentDictionary<string,string>(StringComparer.OrdinalIgnoreCase);
 public static void Save(string path) {
  using(var writer=new BinaryWriter(File.Create(path))) { writer.Write("IDEHASH4"); writer.Write(cache.Count); foreach(var entry in cache) { writer.Write(entry.Key); writer.Write(entry.Value); } }
 }
 public static void Load(string path) {
  using(var reader=new BinaryReader(File.OpenRead(path))) { if(reader.ReadString()!="IDEHASH4") throw new IOException("Invalid cache."); int count=reader.ReadInt32(); if(count<0 || count>1000000) throw new IOException("Invalid cache count."); for(int i=0;i<count;i++) cache[reader.ReadString()]=reader.ReadString(); }
 }
 public static ConcurrentDictionary<string,string> Build(string root,bool preflight) {
  string cacheRoot=root.Replace(".before-move-20261122","");
  bool codex=cacheRoot.EndsWith("\\.codex",StringComparison.OrdinalIgnoreCase);
  var result=new ConcurrentDictionary<string,string>(StringComparer.OrdinalIgnoreCase);
  var dirs=new Stack<string>(); var files=new List<KeyValuePair<string,FileInfo>>(); dirs.Push(root);
  while(dirs.Count>0) foreach(FileSystemInfo entry in new DirectoryInfo(dirs.Pop()).EnumerateFileSystemInfos()) {
   string rel=entry.FullName.Substring(root.Length).TrimStart('\\');
   if(preflight && codex) {
    string top=rel.Split('\\')[0].ToLowerInvariant();
    if(top!=".sandbox-bin" && top!="plugins" && top!="cache" && top!="skills" && top!="vendor_imports") continue;
   }
   if((entry.Attributes & FileAttributes.ReparsePoint)!=0) result[rel]="LINK";
   else if((entry.Attributes & FileAttributes.Directory)!=0) { result[rel]="DIR"; dirs.Push(entry.FullName); }
   else files.Add(new KeyValuePair<string,FileInfo>(rel,(FileInfo)entry));
  }
  Parallel.ForEach(files,new ParallelOptions{MaxDegreeOfParallelism=4},entry=>{
   var file=entry.Value; long length=file.Length; long stamp=file.LastWriteTimeUtc.Ticks;
   string prefix=length+"|"+stamp+"|",cacheKey=cacheRoot+"\\"+entry.Key,cached,digest;
   bool volatileFile=codex && (file.Name.IndexOf(".sqlite",StringComparison.OrdinalIgnoreCase)>=0 || file.Extension==".log" || file.Extension==".jsonl" || file.Extension==".lock");
   if(!volatileFile && cache.TryGetValue(cacheKey,out cached) && cached.StartsWith(prefix,StringComparison.Ordinal)) digest=cached.Substring(prefix.Length);
   else {
    byte[] hash; using(var sha=SHA256.Create()) using(var stream=new FileStream(file.FullName,FileMode.Open,FileAccess.Read,FileShare.Read,131072,FileOptions.SequentialScan)) hash=sha.ComputeHash(stream);
    digest=BitConverter.ToString(hash); if(!volatileFile) cache[cacheKey]=prefix+digest;
   }
   file.Refresh(); if(file.Length!=length || file.LastWriteTimeUtc.Ticks!=stamp) throw new IOException("File changed during verification: "+entry.Key);
   result[entry.Key]="FILE|"+length+"|"+digest;
  });
  return result;
 }
}
'@
function Snapshot([string]$root) {
    $result=[IdeMoveHashV4]::Build($root,($Mode -eq 'Preflight'))
    foreach ($key in @($result.Keys)) {
        if ($result[$key] -eq 'LINK') {
            $link=Get-Item -LiteralPath (Join-Path $root $key) -Force
            $result[$key]='LINK|'+$link.LinkType+'|'+($link.Target -join '|')
        }
    }
    return ,$result
}
function Equal-Snapshots($a,$b) {
    if ($a.Count -ne $b.Count) { throw "Inventory counts differ: $($a.Count) / $($b.Count)" }
    foreach ($key in $a.Keys) { if (-not $b.ContainsKey($key) -or $a[$key] -cne $b[$key]) { throw "Verification mismatch: $key" } }
}
function Delete-Backup($p) {
    Validate-Paths
    if ($p.Backup -notin @('C:\Users\lenovo\.vscode.before-move-20261122','C:\Users\lenovo\.codex.before-move-20261122')) { throw 'Unexpected cleanup target.' }
    Assert-Physical $p.Backup
    $link=Get-Item -LiteralPath $p.Source -Force
    if ($link.LinkType -ne 'Junction' -or $link.Target[0] -ne $p.Target) { throw 'Refusing cleanup without a verified junction.' }
    $stack=[Collections.Generic.Stack[string]]::new(); $dirs=[Collections.Generic.List[string]]::new(); $stack.Push($p.Backup)
    while ($stack.Count -gt 0) {
        $dir=$stack.Pop()
        if ($dir -ne $p.Backup -and -not [IO.Path]::GetFullPath($dir).StartsWith($p.Backup+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Cleanup escaped the backup.' }
        $dirs.Add($dir)
        foreach ($item in Get-ChildItem -LiteralPath $dir -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                if ($item.PSIsContainer) { [IO.Directory]::Delete($item.FullName) } else { [IO.File]::Delete($item.FullName) }
            } elseif ($item.PSIsContainer) { $stack.Push($item.FullName) }
            else { Remove-Item -LiteralPath $item.FullName -Force }
        }
    }
    for ($i=$dirs.Count-1;$i -ge 0;$i--) { [IO.Directory]::Delete($dirs[$i]) }
}
if ($Mode -eq 'Preflight') {
    try {
        State 'Testing' 'Verifying immutable files before closing the editor.'
        Copy-Folders
        $watch=[Diagnostics.Stopwatch]::StartNew()
        $a=Snapshot $pairs[0].Source; Equal-Snapshots $a (Snapshot $pairs[0].Target)
        $known=(Get-FileHash -LiteralPath (Join-Path $pairs[0].Source 'argv.json') -Algorithm SHA256).Hash
        if ((($a['argv.json'] -split '\|')[-1] -replace '-','') -ne $known) { throw 'Hasher did not match Get-FileHash.' }
        $codexStatic=Snapshot $pairs[1].Source; Equal-Snapshots $codexStatic (Snapshot $pairs[1].Target)
        [IdeMoveHashV4]::Save('D:\IDE\migration-cache-v4.bin')
        $fullSeconds=$watch.Elapsed.TotalSeconds
        $watch.Restart()
        $a=Snapshot $pairs[0].Source; Equal-Snapshots $a (Snapshot $pairs[0].Target)
        $codexStatic=Snapshot $pairs[1].Source; Equal-Snapshots $codexStatic (Snapshot $pairs[1].Target)
        State 'Passed' 'VS Code and immutable Codex files verified with SHA-256. Only changed files and volatile databases need hashing after close.' @{Entries=($a.Count+$codexStatic.Count);FullHashSeconds=[math]::Round($fullSeconds,2);WarmCheckSeconds=[math]::Round($watch.Elapsed.TotalSeconds,2);HelperSHA256=(Get-FileHash -LiteralPath $PSCommandPath).Hash}
        exit 0
    } catch { State 'Failed' $_.Exception.GetBaseException().Message @{Position=$_.InvocationInfo.PositionMessage}; exit 1 }
}
$mutex=[Threading.Mutex]::new($false,'Local\MoveVSCodeCodexData20261122')
if (-not $mutex.WaitOne(0)) { exit }
$swapped=[Collections.Generic.List[object]]::new(); $cleaning=$false
try {
    Validate-Paths
    [IdeMoveHashV4]::Load('D:\IDE\migration-cache-v4.bin')
    foreach ($p in $pairs) { Assert-Physical $p.Source; if (Test-Path -LiteralPath $p.Backup) { throw 'A previous backup needs inspection.' } }
    $freeBefore=([IO.DriveInfo]::new('C:\')).AvailableFreeSpace
    State 'RestartingEditor' 'Saved edits confirmed. Temporarily closing VS Code to finish migration.'
    $progress=Join-Path $base 'DANG_CHUYEN.txt'
    @('DANG CHUYEN DU LIEU VS CODE / CODEX SANG O D.','','Vui long cho, KHONG MO LAI VS CODE bang tay.','Chuong trinh se tu mo lai VS Code khi hoan tat.','Bang KET_QUA se hien dung luong thuc te da giai phong tren o C.') | Set-Content -LiteralPath $progress -Encoding UTF8
    Start-Process -FilePath "$env:SystemRoot\System32\notepad.exe" -ArgumentList ('"'+$progress+'"') -WindowStyle Normal
    Start-Sleep -Seconds 8
    foreach ($proc in @(Get-Process -Name Code,codex,codex-code-mode-host -ErrorAction SilentlyContinue)) {
        try { $exe=$proc.Path } catch { $exe=$null }
        if ($exe -and ($exe -eq $editor -or $exe.StartsWith('C:\Users\lenovo\.vscode\',[StringComparison]::OrdinalIgnoreCase) -or $exe.StartsWith('C:\Users\lenovo\.codex\',[StringComparison]::OrdinalIgnoreCase))) { Stop-Process -InputObject $proc -Force -ErrorAction SilentlyContinue }
    }
    :verify while ($true) {
        while (@(Blockers).Count -gt 0) { State 'WaitingForAppsToClose' 'Waiting for VS Code and Codex to exit.'; Start-Sleep -Seconds 3 }
        Start-Sleep -Seconds 1
        if (@(Blockers).Count -gt 0) { continue }
        State 'FinalCopy' 'Refreshing the copies after applications exited.'
        Copy-Folders
        $snapshots=@{}
        try {
            State 'Verifying' 'Checking every file using parallel SHA-256.'
            foreach ($p in $pairs) {
                $snapshots[$p.Source]=Snapshot $p.Source
                $copy=Snapshot $p.Target
                if (@(Blockers).Count -gt 0) { continue verify }
                Equal-Snapshots $snapshots[$p.Source] $copy
            }
        } catch { if (@(Blockers).Count -gt 0) { continue verify }; throw }
        if (@(Blockers).Count -eq 0) { break }
    }
    State 'Switching' 'Replacing original paths with junctions to D.'
    foreach ($p in $pairs) {
        Validate-Paths
        Move-Item -LiteralPath $p.Source -Destination $p.Backup
        $swapped.Add($p)
        New-Item -ItemType Junction -Path $p.Source -Target $p.Target | Out-Null
        $link=Get-Item -LiteralPath $p.Source -Force
        if ($link.LinkType -ne 'Junction' -or $link.Target[0] -ne $p.Target) { throw 'Junction verification failed.' }
        $probeName='.migration-probe-'+[Guid]::NewGuid().ToString('N')
        $probe=Join-Path $p.Source $probeName
        [IO.File]::WriteAllText($probe,'junction-test')
        try { if ([IO.File]::ReadAllText((Join-Path $p.Target $probeName)) -ne 'junction-test') { throw 'Junction write-through failed.' } } finally { [IO.File]::Delete($probe) }
    }
    foreach ($p in $pairs) { Equal-Snapshots $snapshots[$p.Source] (Snapshot $p.Backup) }
    $cleaning=$true
    State 'CleaningVerifiedOriginals' 'Both copies and junctions passed verification. Deleting verified original data from C.'
    foreach ($p in $pairs) { Delete-Backup $p }
    $freed=([IO.DriveInfo]::new('C:\')).AvailableFreeSpace-$freeBefore
    State 'Complete' 'Both original folders have been deleted from C; their paths are junctions to D:\IDE.' @{FreedBytes=$freed;Mappings=$pairs;HelperSHA256=(Get-FileHash -LiteralPath $PSCommandPath).Hash}
    $report=Join-Path $base 'KET_QUA.txt'
    @('DA HOAN TAT.','C:\Users\lenovo\.vscode -> D:\IDE\.vscode','C:\Users\lenovo\.codex -> D:\IDE\.codex',('Da giai phong tren o C: '+[math]::Round($freed/1GB,2)+' GB.'),'Hai duong dan tren C chi la lien ket. Du lieu that nam tren D.','Da kiem tra SHA-256 va xoa ban goc tren C.') | Set-Content -LiteralPath $report -Encoding UTF8
    $staleError=Join-Path $base 'LOI_CHUYEN.txt'
    if (Test-Path -LiteralPath $staleError) { Remove-Item -LiteralPath $staleError -Force }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Start-Process -FilePath $editor -ArgumentList '"D:\AIagent _openworld"' -WindowStyle Normal
    Start-Process -FilePath "$env:SystemRoot\System32\notepad.exe" -ArgumentList ('"'+$report+'"') -WindowStyle Normal
} catch {
    $message=$_.Exception.GetBaseException().Message
    if (-not $cleaning) {
        for ($i=$swapped.Count-1;$i -ge 0;$i--) {
            $p=$swapped[$i]
            try {
                if (Test-Path -LiteralPath $p.Source) {
                    $link=Get-Item -LiteralPath $p.Source -Force
                    if ($link.LinkType -ne 'Junction' -or $link.Target[0] -ne $p.Target) { throw 'Unexpected rollback path.' }
                    [IO.Directory]::Delete($p.Source)
                }
                Move-Item -LiteralPath $p.Backup -Destination $p.Source
            } catch { $message+=' Rollback: '+$_.Exception.Message }
        }
    }
    State 'NeedsAttention' $message @{CleanupStarted=$cleaning;Position=$_.InvocationInfo.PositionMessage;Stack=$_.ScriptStackTrace}
    $report=Join-Path $base 'LOI_CHUYEN.txt'
    @('CHUA HOAN TAT.',$message,'Chi tiet: D:\AIagent _openworld\IDE_MIGRATION\status.json') | Set-Content -LiteralPath $report -Encoding UTF8
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    if (-not (Get-Process -Name Code -ErrorAction SilentlyContinue)) { Start-Process -FilePath $editor -ArgumentList '"D:\AIagent _openworld"' -WindowStyle Normal }
    Start-Process -FilePath "$env:SystemRoot\System32\notepad.exe" -ArgumentList ('"'+$report+'"') -WindowStyle Normal
} finally { $mutex.ReleaseMutex();$mutex.Dispose() }
