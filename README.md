# RDC в DFS Replication: объём передачи при изменении части файла

Материалы к статье: Гаврилова И. В., Козлов П. А. «Влияние использования удалённого
дифференциального сжатия на объём данных, передаваемых службой DFS Replication»
(РГУ нефти и газа (НИУ) имени И. М. Губкина, 2026).

## Что здесь лежит

| Путь | Содержимое |
|---|---|
| `scripts/measure.ps1` | Скрипт одного опыта: проверка состояния реплик, замер счётчика `Total Bytes Received` до и после изменения, ожидание пустой очереди и совпадения SHA-256 на обоих узлах, запись строки в CSV |
| `data/results_v2.csv` | Исходные данные: 91 запись (90 успешных опытов и 1 прерванный, `Status = ERROR`) |
| `analysis/analyze.py` | Медианы, межквартильный размах, бутстреп-интервалы отношения медиан, точный критерий Манна–Уитни, линейная аппроксимация |
| `analysis/charts.py` | Построение рисунков 2–4 статьи |
| `figures/` | Готовые рисунки |

## Стенд

Две виртуальные машины Windows Server 2025 (Oracle VirtualBox, внутренняя сеть
192.168.50.0/24): SRV1 – контроллер домена `company.local` и отправитель, SRV2 –
получатель. Группа репликации `RG1`, папка `C:\DFSShare`, тестовый файл
`bigfile.bin` объёмом 1 073 741 824 байта случайных данных.

## Как повторить опыт

На SRV1 от имени администратора домена:

```powershell
# один уровень объёма изменения, пять повторов
C:\measure.ps1 -ChangeBytes 1048576 -Repeats 5
```

Режим RDC переключается до запуска серии:

```powershell
Set-DfsrConnection -GroupName RG1 -SourceComputerName SRV1 -DestinationComputerName SRV2 -DisableRDC $true
Set-DfsrConnection -GroupName RG1 -SourceComputerName SRV2 -DestinationComputerName SRV1 -DisableRDC $true
Update-DfsrConfigurationFromAD
```

Результаты дописываются в `C:\RDC_Experiment\results_v2.csv`.

## Как пересчитать статистику и рисунки

```bash
pip install pandas numpy scipy matplotlib
cd analysis
python analyze.py ../data/results_v2.csv
python charts.py
```

## Поля CSV

`TrialID`, `Started`, `Finished`, `Status`, `RDCConfigured` (ON/OFF), `FileBytes`,
`ChangeBytes`, `ChangeFraction`, `Offset`, `Repeat`, `Before`, `After`,
`Delta` (байт, принято SRV2 за цикл), `InitialHashSRV1/2`, `FinalHashSRV1/2`,
`HashMatch`, `BacklogSeen`, `FinalBacklog`, `ElapsedSeconds`, `Error`.

## Ограничения

Обе ВМ на одном физическом хосте; случайные данные; замена непрерывного диапазона
без вставки; серии выполнены блоками (сначала все опыты с RDC, затем без RDC);
счётчик не учитывает заголовки TCP/IP; нагрузка на процессор не измерялась.
