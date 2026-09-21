# Models

本專案不將大型模型權重提交至 Git。

第一次執行時，若本機找不到預設 PyTorch 權重，程式會依
`config/config.example.ini` 的 `weights_url` 自動下載。

預設上游模型：

- Hugging Face：`Hansung-Cho/yolov8-ppe-detection`
- 權重檔：`best.pt`

第三方模型權重與 Ultralytics 元件仍受其原始授權條款約束。
重新散布或商業使用前，請自行確認上游授權。

## OpenVINO 匯出

下載 `.pt` 模型後，可於本機執行：

```bash
yolo export model=models/ppe_hansung.pt format=openvino
```

再將 `--weights` 指向輸出的 OpenVINO 模型目錄。
