# PPE 工裝安全辨識 Demo

這是一個經過去識別化處理的作品集 Demo，用於即時辨識 PPE（Personal Protective Equipment，個人防護裝備）。
本專案支援攝影機、影片檔與 RTSP 串流輸入，執行 PPE 模型推論後，會將人員與安全帽／反光背心辨識結果進行關聯，並可選擇將彙整後的安全狀態發佈至 MQTT。

> 此 Repository 為公開作品集／Demo 版本。客戶名稱、實際場域資訊、攝影機帳密、內部網路設定與正式環境參數均已移除。

## 功能特色

- 支援 Webcam／本地影片／RTSP 串流輸入
- 使用 Ultralytics YOLO 執行 PPE 物件辨識
- 人員與安全帽／反光背心辨識結果關聯
- 支援 `OK`、`NO_HELMET`、`NO_VEST` 等安全狀態分類
- 可選擇透過 MQTT 發佈狀態，並提供各 Topic 冷卻時間機制
- 模型於執行時自動下載，不將大型模型權重提交至 Git
- 可延伸使用 OpenVINO 進行 Intel 平台推論加速

## 系統架構

```text
Camera / RTSP / Video
        |
        v
背景影像擷取
        |
        v
YOLO PPE 模型推論
        |
        v
人員 + PPE 關聯判斷
        |
        +----> 即時預覽 / 影像輸出
        |
        +----> MQTT 安全狀態 Topic
```

## 快速開始

### 1. Clone 專案並建立 Python 虛擬環境

```bash
git clone https://github.com/SHIH-KEVIN/ppe-safety-detection-demo.git
cd ppe-safety-detection-demo
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 建立本機設定檔

Windows：

```powershell
Copy-Item config\config.example.ini config\config.ini
```

Linux / macOS：

```bash
cp config/config.example.ini config/config.ini
```

請依自己的影像來源與 MQTT Broker 修改 `config/config.ini`。
`config/config.ini` 已加入 `.gitignore`，避免帳號、密碼或實際環境參數被誤提交至 Git。

### 3. 執行程式

使用設定檔：

```bash
python src/ppe.py --config config/config.ini
```

或直接使用 Webcam 測試：

```bash
python src/ppe.py --source 0 --show
```

第一次執行時，若 `models/ppe_hansung.pt` 不存在，程式會自動從設定的上游來源下載模型。

## MQTT 輸出

MQTT 為選用功能，在範例設定中預設關閉。啟用後，可將不同安全狀態的統計結果發佈至下列 Topic：

```text
demo/PPE/OK
demo/PPE/NO_HELMET
demo/PPE/NO_VEST
demo/PPE/NO_HELMET_NO_VEST
```

範例 Payload：

```json
{
  "status": "NO_HELMET",
  "count": 1,
  "ts": 1760000000
}
```

## OpenVINO / Intel 推論

本 Repository 不直接提交 OpenVINO `.bin` / `.xml` 模型檔。
請先下載 `.pt` 模型，再於本機執行匯出：

```bash
yolo export model=models/ppe_hansung.pt format=openvino
```

匯出完成後，將 `weights` 指向產生的 OpenVINO 模型目錄，並依本機環境選擇可支援的 Intel 推論裝置。

## 自我測試

專案內含一個不需載入模型即可執行的基本邏輯測試：

```bash
python src/ppe.py --selftest
```

另外提供簡易影像來源連線測試：

```bash
python tests/test_video_source.py --source 0
```

## 公開 Repository 安全注意事項

公開截圖或修改設定前，請再次確認 Repository 中沒有包含：

- 攝影機帳號／密碼
- 正式環境的公網或內網 IP
- 客戶名稱或實際場域名稱
- API Key 或 MQTT 帳密
- 含有個資或隱私資訊的真實監視器影像
- 未取得再散布授權的第三方模型權重

## 模型來源與授權

預設模型下載來源為 Hugging Face 公開 Repository：
`Hansung-Cho/yolov8-ppe-detection`

模型權重採執行時下載，本 Repository 不重新散布模型檔。
如需重新散布模型或用於商業用途，請自行確認上游模型與 Ultralytics 的授權條款。

## AI 輔助開發

本專案開發過程使用 AI Coding 工具協助原型建立、除錯、程式重構與文件整理。
系統架構、串流處理、PPE 狀態判斷邏輯、MQTT 行為、測試流程與最終整合驗證，仍由開發者負責設計與確認。

## 專案定位

本專案主要用於展示以下能力：

- AI 視覺辨識整合
- RTSP／即時串流處理
- Python 應用開發
- MQTT 工業通訊整合
- 模型部署與 OpenVINO 推論流程
- AI 輔助工程開發與系統驗證
