param(
    [ValidateRange(1, 1073741824)]
    [long]$ChangeBytes = 1,
    [ValidateRange(1, 100)]
    [int]$Repeats = 5
)

$ErrorActionPreference = "Stop"
$path = "C:\DFSShare\bigfile.bin"
$outDir = "C:\RDC_Experiment"
$timeoutSec = 1200

New-Item -ItemType Directory -Path $outDir -Force | Out-Null

function Get-Received {
    Invoke-Command -ComputerName "SRV2.company.local" -ErrorAction Stop -ScriptBlock {
        $ErrorActionPreference = "Stop"
        $samples = @(
            (Get-Counter '\DFS Replication Connections(*)\Total Bytes Received').CounterSamples |
                Where-Object InstanceName -like 'srv1.company.local-*'
        )
        if ($samples.Count -ne 1 -or $samples[0].Status -ne 0) {
            throw "Счётчик SRV2 отсутствует, неоднозначен или неисправен."
        }
        [long]$samples[0].RawValue
    }
}

function Get-Queue {
    @(Get-DfsrBacklog -GroupName "RG1" -FolderName "DFSShare" `
        -SourceComputerName "SRV1" -DestinationComputerName "SRV2" `
        -ErrorAction Stop).Count
}

function Get-RemoteFile {
    Invoke-Command -ComputerName "SRV2.company.local" -ErrorAction Stop -ScriptBlock {
        $ErrorActionPreference = "Stop"
        $file = Get-Item -LiteralPath "C:\DFSShare\bigfile.bin"
        [pscustomobject]@{
            Size = $file.Length
            Hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        }
    }
}

function Assert-States {
    $localState = @(
        Get-CimInstance -Namespace "root\MicrosoftDFS" `
            -ClassName "DfsrReplicatedFolderInfo" |
            Where-Object {
                $_.ReplicationGroupName -eq "RG1" -and
                $_.ReplicatedFolderName -eq "DFSShare"
            }
    )

    $remoteState = @(
        Invoke-Command -ComputerName "SRV2.company.local" -ErrorAction Stop -ScriptBlock {
            Get-CimInstance -Namespace "root\MicrosoftDFS" `
                -ClassName "DfsrReplicatedFolderInfo" -ErrorAction Stop |
                Where-Object {
                    $_.ReplicationGroupName -eq "RG1" -and
                    $_.ReplicatedFolderName -eq "DFSShare"
                } |
                Select-Object -ExpandProperty State
        }
    )

    if ($localState.Count -ne 1 -or $remoteState.Count -ne 1) {
        throw "Не удалось однозначно определить состояние папки."
    }
    if ($localState[0].State -ne 4 -or $remoteState[0] -ne 4) {
        throw "Состояние репликации не равно 4 на обоих серверах."
    }
}

function Get-StableReceived {
    $clock = [Diagnostics.Stopwatch]::StartNew()
    $previous = Get-Received
    $stable = 0

    while ($clock.Elapsed.TotalSeconds -lt 90) {
        Start-Sleep -Seconds 5
        $current = Get-Received

        if ($current -lt $previous) {
            throw "Счётчик уменьшился или был сброшен."
        }

        if ($current -eq $previous) {
            $stable++
        }
        else {
            $stable = 0
        }

        if ($stable -ge 3) {
            return $current
        }

        $previous = $current
    }

    throw "Счётчик не стабилизировался за 90 секунд."
}

for ($i = 1; $i -le $Repeats; $i++) {
    $row = [ordered]@{
        TrialID = [guid]::NewGuid().ToString()
        Started = (Get-Date).ToString("o")
        Finished = ""
        Status = "ERROR"
        RDCConfigured = ""
        FileBytes = 0
        ChangeBytes = $ChangeBytes
        ChangeFraction = 0
        Offset = 0
        Repeat = $i
        Before = $null
        After = $null
        Delta = $null
        InitialHashSRV1 = ""
        InitialHashSRV2 = ""
        FinalHashSRV1 = ""
        FinalHashSRV2 = ""
        HashMatch = $false
        BacklogSeen = $false
        FinalBacklog = $null
        ElapsedSeconds = $null
        Error = ""
    }

    $clock = [Diagnostics.Stopwatch]::StartNew()

    try {
        Assert-States

        $connections = @(Get-DfsrConnection -GroupName "RG1")
        $forward = @($connections | Where-Object {
            $_.SourceComputerName -eq "SRV1" -and
            $_.DestinationComputerName -eq "SRV2"
        })
        $reverse = @($connections | Where-Object {
            $_.SourceComputerName -eq "SRV2" -and
            $_.DestinationComputerName -eq "SRV1"
        })

        if ($forward.Count -ne 1 -or $reverse.Count -ne 1) {
            throw "Не найдены оба соединения RG1."
        }
        if (-not $forward[0].Enabled -or -not $reverse[0].Enabled) {
            throw "Одно из соединений выключено."
        }
        if ($forward[0].RdcEnabled -ne $reverse[0].RdcEnabled) {
            throw "Настройки RDC в направлениях различаются."
        }

        $row.RDCConfigured = if ($forward[0].RdcEnabled) { "ON" } else { "OFF" }

        $file = Get-Item -LiteralPath $path
        $row.FileBytes = $file.Length

        if ($file.Length -ne 1073741824) {
            throw "Размер исходного файла отличается от 1 GiB."
        }
        if ($ChangeBytes -gt $file.Length) {
            throw "Диапазон изменения больше файла."
        }

        $row.ChangeFraction = $ChangeBytes / [double]$file.Length
        $row.Offset = [long][Math]::Min(500000000, $file.Length - $ChangeBytes)

        $expected = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        $row.InitialHashSRV1 = $expected

        $wait = [Diagnostics.Stopwatch]::StartNew()

        do {
            $remote = Get-RemoteFile
            $queue = Get-Queue

            if ($remote.Size -eq $file.Length -and
                $remote.Hash -eq $expected -and $queue -eq 0) {
                break
            }

            if ($wait.Elapsed.TotalSeconds -ge $timeoutSec) {
                throw "Начальная синхронизация не подтверждена за 20 минут."
            }

            Start-Sleep -Seconds 5
        } while ($true)

        $row.InitialHashSRV2 = $remote.Hash
        $row.Before = Get-StableReceived

        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        $buffer = New-Object byte[] 1048576
        $mask = New-Object byte[] 1048576
        $stream = $null

        try {
            $stream = [IO.File]::Open(
                $path,
                [IO.FileMode]::Open,
                [IO.FileAccess]::ReadWrite,
                [IO.FileShare]::None
            )

            $position = [long]$row.Offset
            $remaining = $ChangeBytes

            while ($remaining -gt 0) {
                $count = [int][Math]::Min($buffer.Length, $remaining)
                $stream.Position = $position
                $read = 0

                while ($read -lt $count) {
                    $n = $stream.Read($buffer, $read, $count - $read)
                    if ($n -eq 0) {
                        throw "Неожиданный конец файла."
                    }
                    $read += $n
                }

                $rng.GetNonZeroBytes($mask)

                for ($j = 0; $j -lt $count; $j++) {
                    $buffer[$j] = $buffer[$j] -bxor $mask[$j]
                }

                $stream.Position = $position
                $stream.Write($buffer, 0, $count)
                $position += $count
                $remaining -= $count
            }

            $stream.Flush($true)
        }
        finally {
            if ($null -ne $stream) {
                $stream.Dispose()
            }
            $rng.Dispose()
        }

        $wait.Restart()
        $queue = Get-Queue
        if ($queue -gt 0) {
            $row.BacklogSeen = $true
        }

        $expected = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        $row.FinalHashSRV1 = $expected

        if ($expected -eq $row.InitialHashSRV1) {
            throw "После записи SHA-256 не изменился."
        }

        do {
            $queue = Get-Queue
            if ($queue -gt 0) {
                $row.BacklogSeen = $true
            }

            $remote = Get-RemoteFile

            if ($remote.Size -eq $file.Length -and
                $remote.Hash -eq $expected -and $queue -eq 0) {
                break
            }

            if ($wait.Elapsed.TotalSeconds -ge $timeoutSec) {
                throw "Репликация не подтверждена за 20 минут."
            }

            Start-Sleep -Seconds 5
        } while ($true)

        $row.After = Get-StableReceived

        Assert-States

        $row.FinalHashSRV1 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        $remote = Get-RemoteFile
        $row.FinalHashSRV2 = $remote.Hash
        $row.FinalBacklog = Get-Queue
        $row.HashMatch = (
            $row.FinalHashSRV1 -eq $expected -and
            $row.FinalHashSRV2 -eq $expected
        )

        if (-not $row.HashMatch -or $row.FinalBacklog -ne 0) {
            throw "Конечная проверка хэшей или очереди не пройдена."
        }

        $row.Delta = [long]$row.After - [long]$row.Before
        if ($row.Delta -le 0) {
            throw "Нулевая или отрицательная дельта счётчика."
        }

        $row.Status = "OK"
    }
    catch {
        $row.Error = $_.Exception.Message
    }

    $row.Finished = (Get-Date).ToString("o")
    $row.ElapsedSeconds = [Math]::Round($clock.Elapsed.TotalSeconds, 1)

    [pscustomobject]$row |
        Export-Csv "$outDir\results_v2.csv" -Append -NoTypeInformation -Encoding UTF8

    [pscustomobject]$row |
        Format-List Status, RDCConfigured, ChangeBytes, Repeat, Delta,
            HashMatch, BacklogSeen, FinalBacklog, ElapsedSeconds, Error

    if ($row.Status -ne "OK") {
        throw "Эксперимент остановлен. Ошибка сохранена в results_v2.csv."
    }
}
