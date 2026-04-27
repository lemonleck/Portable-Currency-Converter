# 便携汇率转换工具

一个无第三方依赖的 Python 桌面 GUI 工具，用于人民币与美元、欧元、英镑之间转换。

## 功能

- 支持人民币与 USD/EUR/GBP 双向转换。
- 同时显示公司固定汇率计算结果和实时汇率计算结果。
- 默认公司汇率：
  - 1 USD = 6.6 CNY
  - 1 EUR = 7.2 CNY
  - 1 GBP = 8.9 CNY
- 可在界面中修改公司汇率，配置保存在 `company_rates.json`。
- 实时汇率使用 `https://api.frankfurter.dev/v1/latest?base=...&symbols=...`，无需 API Key。

## 运行

Windows 上推荐双击 `run.vbs` 启动，它不会显示黑色命令行窗口。

也可以双击 `run.bat`，它会使用 `pythonw` 启动程序，并自动关闭命令行窗口。

或在当前目录执行：

```powershell
python app.py
```

如果实时汇率不可用，工具仍会显示公司固定汇率结果。
