# PromptDB on Colab

通用 PromptDB 安裝工具，沿用 Isi-dev/Google-Colab_Notebooks 的 fork。
根目錄 `ComfyUI_PromptDB.ipynb` 是單一 Krea2 notebook，包含 Drive 掛載、提示 JSON 上傳與自動載入、
模型下載與 Drive 快取、原工作流需要的節點，以及 Cloudflare Tunnel 直連。
首次上傳請勾選 `upload_prompt`，選取一般用途 `prompt_defalut.json` 或其他名稱的 JSON。
檔案保存在 `MyDrive/ComfyUI-PromptDB/user-db/`，目前選擇記在 `active_prompt.json`。
下次不勾選上傳即可自動載入上次選擇；首次沒有資料則建立一般旅拍範例。
提示格式是分類 → 提示名稱 → 字串。覆蓋同名檔案前會備份，資料庫連結到 Drive，因此節點儲存修改也會保留。
執行「全部執行」後，在最後一格點「開啟 ComfyUI」。Drive 授權須由使用者自行完成。
本次單一 notebook 的語法、整合與上傳備份檢查通過；Drive 授權及新 notebook 全程重跑尚未驗證。
`ComfyUI/` 底下全部 17 份 notebooks 也已加入相同整合；各自保留其原有功能，
不代表原本沒有 Manager 的 notebook 會額外安裝 Manager。

若使用 `ComfyUI/` 中保留的上游 notebooks，選 GPU runtime，先執行新增的「PromptDB：安裝與私人 Drive 選項」，再依序執行原儲存格。
PromptDB 會在原程式啟動 ComfyUI 前安裝，因此不需另開精簡 notebook 或重啟服務。
Z-Image 原本使用直接出圖介面而非 ComfyUI 網頁；保留此介面，在 Generate Image
儲存格新增資料庫／分類／名稱欄位，留空則使用原提示文字。

## Google Drive 模型快取

勾選 `models_use_drive`，模型會下載到 `promptdb_drive_folder/models/`，預設為
`/content/drive/MyDrive/ComfyUI-PromptDB/models/`。這與 `promptdb_use_drive` 的提示庫匯入選項獨立。
每次新開 runtime 都要重新掛載 Drive、安裝 ComfyUI 與節點；模型檔案可以沿用。
設定會在原 notebook 的模型下載程式執行前，把 runtime 的 `ComfyUI/models` 連到 Drive。
原下載器可依既有檔案或續傳機制重用檔案；原專案使用時間戳命名的 Civitai 自訂下載仍可能另存新檔。
Drive 讀取通常比 runtime 本機磁碟慢；這個選項不省略模型載入所需的 RAM／VRAM。
若已在本次 runtime 下載模型，工具會保留那些檔案並停止，不會自動搬移或覆寫；請在新 runtime 一開始啟用。
Drive 掛載與跨次 runtime 重用仍需實測，不應只憑本機連結測試宣稱已驗證。
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
範例沿用原本的模型檔名；權重檔案不直接附在 Git repository。
勾選 `download_krea2_models` 可下載原工作流的 V2 NVFP4、Qwen3-VL 編碼器與 VAE，
約 13.66 GB，來源與 SHA256 固定在 `models.krea2.json`；需遵循來源的 Krea 2 community license。

## 從 Colab 開啟網頁

安裝會在 ComfyUI `server.py` 加入一項窄範圍相容性修正：僅允許跨站的
`GET /` 頂層頁面導航（`navigate/document`）。這讓 Colab 的 Tunnel 連結能開啟首頁。
跨站 API、POST、iframe 與後續 Host／Origin 檢查維持原限制，未全面開啟 CORS。
修改前的檔案保留為 `server.py.promptdb-before-navigation.bak`；若上游程式結構不符會停止並提示。
如瀏覽器禁止 Colab 輸出元件的 Cookie，可使用原 notebook 的 `use_cloudflare` 選項。
Cloudflare 臨時網址會公開該 runtime 的 ComfyUI，結束 runtime 後失效。
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

2026-10-26 已在指定帳號的 Colab T4 實測：ComfyUI 0.42.0、前端 1.57.1、
全部 37 個節點的範例載入、分類選單切換與提示文字更新、原 Neutrino V2 NVFP4 模型
256×256／2 steps 出圖及網頁圖片預覽。這是執行驗證，不代表 832×1216／10 steps 的效能或畫質也已驗收。
已另外點擊網頁「執行」按鈕完成第二張 PNG，確認不只 API 可以送出任務。
`Krea2_PromptDB_Quick_Test.json` 保留相同 37 個節點與連線，預設 256×256／2 steps，方便先驗證環境。
原生 Colab proxy 的輸出元件曾受瀏覽器 Cookie 問題影響；本次網頁驗收使用 Cloudflare Tunnel。
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
