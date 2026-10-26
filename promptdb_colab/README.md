# PromptDB on Colab

通用 PromptDB 安裝工具，沿用 Isi-dev/Google-Colab_Notebooks 的 fork。
根目錄 `ComfyUI_PromptDB.ipynb` 現在使用原專案完整 FLUX.1-dev USO ComfyUI notebook，
包含其模型下載、自訂節點安裝、ComfyUI-Manager、Cloudflare／Colab 視窗連線選項與原有 VRAM 判斷。
`ComfyUI/` 底下全部 17 份 notebooks 也已加入相同整合；各自保留其原有功能，
不代表原本沒有 Manager 的 notebook 會額外安裝 Manager。

選 GPU runtime，先執行新增的「PromptDB：安裝與私人 Drive 選項」，再依序執行原儲存格。
PromptDB 會在原程式啟動 ComfyUI 前安裝，因此不需另開精簡 notebook 或重啟服務。
Z-Image 原本使用直接出圖介面而非 ComfyUI 網頁；保留此介面，在 Generate Image
儲存格新增資料庫／分類／名稱欄位，留空則使用原提示文字。
本版本只附一般風景範例，不包含本地提示庫、私人圖片、成人生成工作流或專用模型。

## 私人資料

選擇掛載 Drive 後，將一般用途的提示 JSON 放入
`MyDrive/ComfyUI-PromptDB/user-db/prompts.json` 及 `prompts_krea2.json`。
格式是 `{"分類": {"名稱": "提示文字"}}`。安裝會驗證格式，不覆寫不同的既有資料。
工作流放在同一個 Drive 資料夾的 `workflows/`；啟動前會匯入
`ComfyUI/user/default/workflows/PromptDB-Drive/`，用 ComfyUI 的 Open 選擇載入。
既有同名但不同內容的工作流不會被覆寫。
已附 PromptDB、Krea2CastPick 與四輸入的 TextJoinV2 相容節點；其餘模型／取樣／預覽節點使用 ComfyUI 內建版本。
角色抽選保留原解析及標記處理，群像預設描述與缺少角色時的替代文字改為一般用途。
`examples/PROMPT.JSON` 是可下載的範例；實際載入檔名仍為 `prompts.json` 和 `prompts_krea2.json`。
`examples/workflows/Krea2_PromptDB_Example.json` 保留原 `Krea2_Neutrino_PromptDB.json`
全部 37 個節點、節點 ID、輸入輸出與連線，只更換提示、說明及輸出檔名前綴。
安裝時會自動將此範例放進 `workflows/PromptDB-Drive/`。
範例沿用原本的模型檔名；模型尚未隨範例上傳或下載，開啟介面不代表可以使用該模型出圖。
在畫面上重新選擇資料庫、分類與提示，將 STRING 接到文字編碼器。

## 模型與節點

`models.example.json` 是空清單，沒有預設下載模型。自行建立一般模型清單：

```json
[{"path": "vae/example.safetensors", "url": "https://example.org/example.safetensors", "sha256": "填入來源提供的64字元SHA256"}]
```

模型需要正確授權、可用下載網址與雜湊。私人或 gated 模型可自行放進 runtime 的
`ComfyUI/models` 正確子資料夾，勿將權杖寫進 notebook 或 Git。
可在 ComfyUI 啟動後用 `setup.py` 的 `audit(comfy, workflows, endpoint)` 報告未找到的節點與模型；
它只掃描 UI 工作流第一層的模型檔名字串，
不代表模型相容、子圖依賴完整或 GPU 記憶體足夠。遇到缺少節點時，先查閱其官方安裝需求。
不會自動安裝工作流宣稱需要的任意程式碼。

Colab 啟動與 GPU 出圖尚未實測。GPU 配額、VRAM、模型載入及 UI proxy 均須在實際 runtime 驗證。
安裝第三方套件及執行節點不構成安全隔離；掛載 Drive 會讓 runtime 能存取 Drive 資料。

本機驗證：`python promptdb_colab/test_setup.py` 及 `python promptdb_colab/test_integration.py`。
整合測試對照 fork 的上游基底，逐份確認 17 份 notebook 的原程式內容保留，並檢查插入順序。
一般 unittest discovery 會嘗試載入
ComfyUI 節點套件，因此在沒有 ComfyUI Python 環境時應使用此直接執行方式。

## 來源與授權

`node/prompt_db.py`、`node/cast_compat.py`、`node/web/prompt_db.js`、`node/web/prompt_db.css` 來自本機修改版
[benstaniford/comfy-prompt-db](https://github.com/benstaniford/comfy-prompt-db)。
保留原始 GPL 授權於 `node/LICENSE`。`node/__init__.py` 註冊上述三個通用／相容節點。
安裝腳本、notebook 與此整合目錄中的新增程式亦採用同一 GPL 授權。
