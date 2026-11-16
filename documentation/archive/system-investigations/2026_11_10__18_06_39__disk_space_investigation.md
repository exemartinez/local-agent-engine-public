# Disk-space investigation

Read-only investigation on 2026-11-10. No files deleted.

- C: free: 6.94 GB. Earlier recorded free space: 56.67 GB on 2026-11-08, 38.61 GB on 2026-11-09 and 8.39 GB on 2026-11-10. Net 56.67 to 6.94 change is -49.73 GB. The intermediate 8.39 to 6.94 change is -1.45 GB. Measurements were at different times; free space can fluctuate.
- `benchmarks/api_sync/model-downloads` is empty; latest queue recorded no cleanup error. This establishes no retained files in that location, not proof of all causes of volume usage.
- `***` is 25.77 GB logical, allocation 24,576 MiB, the same 24 GiB setting observed before these benchmarks; current usage was 558 MiB. Hibernation file 6.77 GB logical. This does not substantiate pagefile growth as the cause. Neither was changed.
- A new Ollama update installer was found at `***`, 1.86 GB, modified 2026-11-09. Its current presence is a factual candidate, but the full amount is not necessarily net disk growth. It was not removed.
- Comparison of 2026-11-07 and 2026-11-10 read-only inventories found ***
- Per-run model samples show disk free while model files were present: GLM Q4 36.01 GB, Qwen IQ3 25.02 GB, Qwen IQ2 27.21 GB, Qwen Q4 16.35 GB. These are different times and include the active model download; they do not account for later disk loss.
- New inventory scanned 1,071,968 files, recorded 134 access/metadata errors, and skipped 198 reparse points. Protected storage is therefore not fully accounted for. The current user's Recycle Bin shell view showed zero items; this does not establish that other accounts' bins are empty.
- `vssadmin list shadowstorage` was attempted read-only and failed for insufficient privileges. Shadow storage and other protected usage remain unknown. Do not attribute the missing space to snapshots without an authorized measurement.

Evidence: `benchmarks/results/2026_11_07__13_25_16__disk_inventory.json`, `benchmarks/results/2026_11_10__18_02_57__disk_inventory.json`, and the corresponding timestamped documentation files. No model download should start with insufficient disk reserve.
