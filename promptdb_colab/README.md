# PromptDB on Colab

通用 PromptDB 安裝工具，沿用 Isi-dev/Google-Colab_Notebooks 的 fork。
開啟根目錄 `ComfyUI_PromptDB.ipynb`，選 GPU runtime，依序執行。
本版本只附一般風景範例，不包含本地提示庫、私人圖片、成人生成工作流或專用模型。

## 私人資料

選擇掛載 Drive 後，將一般用途的提示 JSON 放入
`MyDrive/ComfyUI-PromptDB/user-db/prompts.json` 及 `prompts_krea2.json`。
格式是 `{"分類": {"名稱": "提示文字"}}`。安裝會驗證格式，不覆寫不同的既有資料。
工作流放在同一個 Drive 資料夾的 `workflows/`；用 ComfyUI 的 Open 選擇載入。
只有 PromptDB 節點已打包；PromptStack、角色抽選與其他自訂節點需要另外處理。
在畫面上重新選擇資料庫、分類與提示，將 STRING 接到文字編碼器。

## 模型與節點

`models.example.json` 是空清單，沒有預設下載模型。自行建立一般模型清單：

```json
[{"path": "vae/example.safetensors", "url": "https://example.org/example.safetensors", "sha256": "填入來源提供的64字元SHA256"}]
```

模型需要正確授權、可用下載網址與雜湊。私人或 gated 模型可自行放進 runtime 的
`ComfyUI/models` 正確子資料夾，勿將權杖寫進 notebook 或 Git。
檢查儲存格會報告工作流中未找到的節點與模型；它只掃描 UI 工作流第一層的模型檔名字串，
不代表模型相容、子圖依賴完整或 GPU 記憶體足夠。遇到缺少節點時，先查閱其官方安裝需求。
不會自動安裝工作流宣稱需要的任意程式碼。

Colab 啟動與 GPU 出圖尚未實測。GPU 配額、VRAM、模型載入及 UI proxy 均須在實際 runtime 驗證。
安裝第三方套件及執行節點不構成安全隔離；掛載 Drive 會讓 runtime 能存取 Drive 資料。

本機驗證：`python promptdb_colab/test_setup.py`。一般 unittest discovery 會嘗試載入
ComfyUI 節點套件，因此在沒有 ComfyUI Python 環境時應使用此直接執行方式。

## 來源與授權

`node/prompt_db.py`、`node/web/prompt_db.js`、`node/web/prompt_db.css` 來自本機修改版
[benstaniford/comfy-prompt-db](https://github.com/benstaniford/comfy-prompt-db)。
保留原始 GPL 授權於 `node/LICENSE`。`node/__init__.py` 改為只註冊通用 PromptDB。
安裝腳本、notebook 與此整合目錄中的新增程式亦採用同一 GPL 授權。
