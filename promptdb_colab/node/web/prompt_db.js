import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Extension for Prompt DB
app.registerExtension({
    name: "PromptDB",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        
        if (nodeData.name === "PromptDB") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            
            nodeType.prototype.onNodeCreated = function() {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                // Find the input widgets
                const categoryWidget = this.widgets?.find(w => w.name === "category");
                const promptNameWidget = this.widgets?.find(w => w.name === "prompt_name");
                const promptTextWidget = this.widgets?.find(w => w.name === "prompt_text");
                const databaseWidget = this.widgets?.find(w => w.name === "database");
                
                if (categoryWidget && promptNameWidget && promptTextWidget) {
                    const getDatabase = () => databaseWidget?.value || "illustrious";
                    let categoryRequestId = 0;
                    let promptListRequestId = 0;
                    let promptTextRequestId = 0;
                    let initializationTimer = null;
                    let promptListReady = false;
                    let loadedDatabase = null;
                    let loadedCategory = null;

                    // ComfyUI can share the options object, not just its values array.
                    categoryWidget.options = { ...categoryWidget.options,
                        values: [...(categoryWidget.options.values || [])] };
                    promptNameWidget.options = { ...promptNameWidget.options, values: [] };
                    const suspendPromptNames = () => {
                        promptListReady = false;
                        promptNameWidget.options.values = [];
                        promptNameWidget.disabled = true;
                        if (promptNameWidget.inputEl) {
                            promptNameWidget.inputEl.innerHTML = "";
                            promptNameWidget.inputEl.disabled = true;
                        }
                        this.setDirtyCanvas(true, true);
                    };
                    suspendPromptNames();

                    const currentPromptText = () => {
                        const inputValue = promptTextWidget.inputEl?.value;
                        return typeof inputValue === "string" ? inputValue : (promptTextWidget.value || "");
                    };
                    
                    // Function to load prompts for a category
                    const loadPrompts = async (category, preserveCurrentSelection = false, desiredPromptName = null, preservePromptText = false) => {
                        const requestId = ++promptListRequestId;
                        const database = getDatabase();
                        const targetSelection = desiredPromptName ?? promptNameWidget.value;
                        const promptTextAtRequestStart = currentPromptText();
                        suspendPromptNames();
                        // A new category/database list supersedes any text request for the old selection.
                        promptTextRequestId++;
                        try {
                            const response = await api.fetchApi("/prompt_db_prompts", {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/json",
                                },
                                body: JSON.stringify({
                                    category: category,
                                    database
                                })
                            });
                            
                            if (response.ok) {
                                const data = await response.json();
                                if (requestId !== promptListRequestId ||
                                    getDatabase() !== database ||
                                    categoryWidget.value !== category) {
                                    return;
                                }
                                
                                // Update the prompt name dropdown values
                                if (data.prompts && data.prompts.length > 0) {
                                    // Own array per node. The server combo is shared across
                                    // every PromptDB node, so replacing the reference is what
                                    // keeps 風格 from listing every other category.
                                    const own = data.prompts.slice();
                                    promptNameWidget.options.values = own;
                                    
                                    // Use desiredPromptName if provided, otherwise preserve current selection
                                    let targetPrompt = targetSelection;
                                    if (!data.prompts.includes(targetPrompt)) {
                                        targetPrompt = data.prompts[0];
                                    }
                                    promptNameWidget.value = targetPrompt;
                                    
                                    // If widget has an input element, update it
                                    if (promptNameWidget.inputEl) {
                                        promptNameWidget.inputEl.innerHTML = "";
                                        data.prompts.forEach(prompt => {
                                            const option = document.createElement("option");
                                            option.value = prompt;
                                            option.textContent = prompt;
                                            promptNameWidget.inputEl.appendChild(option);
                                        });
                                        promptNameWidget.inputEl.value = promptNameWidget.value;
                                    }
                                    loadedDatabase = database;
                                    loadedCategory = category;
                                    promptListReady = true;
                                    promptNameWidget.disabled = false;
                                    if (promptNameWidget.inputEl) promptNameWidget.inputEl.disabled = false;
                                    nodeInstance.setDirtyCanvas(true, true);
                                    
                                    // Load text for the current prompt (not necessarily the first one)
                                    if (!preservePromptText && currentPromptText() === promptTextAtRequestStart) {
                                        await loadPromptText(category, promptNameWidget.value);
                                    }
                                } else {
                                    promptNameWidget.options.values = [];
                                    promptNameWidget.value = "";
                                    if (promptNameWidget.inputEl) promptNameWidget.inputEl.innerHTML = "";
                                    // A user edit made while the list was loading belongs to them.
                                    if (!preservePromptText && currentPromptText() === promptTextAtRequestStart) {
                                        promptTextWidget.value = "";
                                        if (promptTextWidget.inputEl) promptTextWidget.inputEl.value = "";
                                    }
                                    nodeInstance.setDirtyCanvas(true, true);
                                }
                            }
                        } catch (error) {
                            console.error("Error loading prompts:", error);
                        }
                    };
                    
                    // Function to load prompt text
                    const loadPromptText = async (category, promptName) => {
                        const requestId = ++promptTextRequestId;
                        const database = getDatabase();
                        const promptTextAtRequestStart = currentPromptText();
                        try {
                            const response = await api.fetchApi("/prompt_db_text", {
                                method: "POST",
                                headers: {
                                    "Content-Type": "application/json",
                                },
                                body: JSON.stringify({
                                    category: category,
                                    prompt_name: promptName,
                                    database
                                })
                            });
                            
                            if (response.ok) {
                                const data = await response.json();
                                if (requestId !== promptTextRequestId ||
                                    getDatabase() !== database ||
                                    categoryWidget.value !== category ||
                                    promptNameWidget.value !== promptName ||
                                    currentPromptText() !== promptTextAtRequestStart) {
                                    return;
                                }
                                
                                promptTextWidget.value = data.prompt_text || "";
                                
                                // Update the text area DOM element if it exists
                                if (promptTextWidget.inputEl) {
                                    promptTextWidget.inputEl.value = data.prompt_text || "";
                                }
                                
                                // Trigger the callback to update the node
                                if (promptTextWidget.callback) {
                                    promptTextWidget.callback(data.prompt_text || "");
                                }
                                
                                // Force canvas redraw to show changes
                                nodeInstance.setDirtyCanvas(true, true);
                            }
                        } catch (error) {
                            console.error("Error loading prompt text:", error);
                        }
                    };
                    
                    // Store original callbacks
                    const originalCategoryCallback = categoryWidget.callback;
                    const originalPromptNameCallback = promptNameWidget.callback;
                    
                    // Store reference to the node instance
                    const nodeInstance = this;
                    let saveButton = null;
                    let newCategoryWidget = null;
                    let newPromptNameWidget = null;

                    const originalComputeSize = this.computeSize.bind(this);
                    this.computeSize = function() {
                        const size = originalComputeSize(...arguments);
                        size[0] = Math.min(size[0], 420);
                        size[1] = Math.min(size[1], 285);
                        return size;
                    };

                    const setWidgetCompactSize = (widget, height) => {
                        if (!widget) return;
                        widget.computeSize = (width) => [Math.max(140, width - 30), height];
                    };

                    const applyCompactLayout = () => {
                        // Keep PromptDB node compact so it matches the tighter layout.
                        const maxNodeWidth = 420;
                        const maxNodeHeight = 285;

                        if (Array.isArray(nodeInstance.size)) {
                            nodeInstance.size[0] = Math.min(nodeInstance.size[0], maxNodeWidth);
                            nodeInstance.size[1] = Math.min(nodeInstance.size[1], maxNodeHeight);
                        }

                        if (promptTextWidget?.inputEl) {
                            promptTextWidget.inputEl.style.minHeight = "72px";
                            promptTextWidget.inputEl.style.height = "72px";
                        }

                        if (newCategoryWidget?.inputEl) {
                            newCategoryWidget.inputEl.style.height = "30px";
                        }
                        if (newPromptNameWidget?.inputEl) {
                            newPromptNameWidget.inputEl.style.height = "30px";
                        }

                        if (saveButton) {
                            saveButton.computeSize = () => [110, 22];
                        }
                    };
                    
                    // Keep prompt_text widget visible for manual editing and inspection
                    promptTextWidget.hidden = false;
                    setWidgetCompactSize(promptTextWidget, 72);

                    const applyCombo = (widget, values) => {
                        if (!widget || !values) return;
                        widget.options.values = values.slice();
                        if (!values.includes(widget.value)) {
                            widget.value = values[0] || "";
                        }
                        if (widget.inputEl) {
                            widget.inputEl.innerHTML = "";
                            values.forEach((item) => {
                                const option = document.createElement("option");
                                option.value = item;
                                option.textContent = item;
                                widget.inputEl.appendChild(option);
                            });
                            widget.inputEl.value = widget.value;
                        }
                    };

                    const refreshCategories = async () => {
                        const requestId = ++categoryRequestId;
                        const database = getDatabase();
                        try {
                            const response = await api.fetchApi("/prompt_db_categories", {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ database })
                            });
                            if (!response.ok) {
                                return requestId === categoryRequestId && getDatabase() === database;
                            }
                            const data = await response.json();
                            if (requestId !== categoryRequestId || getDatabase() !== database) {
                                return false;
                            }
                            applyCombo(categoryWidget, data.categories || []);
                            return true;
                        } catch (error) {
                            console.error("Error loading categories:", error);
                            return requestId === categoryRequestId && getDatabase() === database;
                        }
                    };

                    if (databaseWidget) {
                        const originalDatabaseCallback = databaseWidget.callback;
                        databaseWidget.callback = function(value) {
                            if (originalDatabaseCallback) {
                                originalDatabaseCallback.call(this, value);
                            }
                            promptListRequestId++;
                            promptTextRequestId++;
                            clearTimeout(initializationTimer);
                            suspendPromptNames();
                            refreshCategories().then((isCurrent) => {
                                if (isCurrent && categoryWidget.value) {
                                    loadPrompts(categoryWidget.value);
                                }
                            });
                        };
                    }

                    // Override category widget callback
                    categoryWidget.callback = function(value) {
                        if (originalCategoryCallback) {
                            originalCategoryCallback.call(this, value);
                        }
                        categoryRequestId++;
                        promptListRequestId++;
                        promptTextRequestId++;
                        clearTimeout(initializationTimer);
                        suspendPromptNames();
                        if (value) {
                            loadPrompts(value);
                        }
                    };
                    
                    // Override prompt name widget callback
                    promptNameWidget.callback = function(value) {
                        if (!promptListReady || loadedDatabase !== getDatabase() ||
                            loadedCategory !== categoryWidget.value ||
                            !promptNameWidget.options.values.includes(value)) return;
                        if (originalPromptNameCallback) {
                            originalPromptNameCallback.call(this, value);
                        }
                        if (value && categoryWidget.value) {
                            loadPromptText(categoryWidget.value, value);
                        }
                    };
                    setWidgetCompactSize(categoryWidget, 22);
                    setWidgetCompactSize(promptNameWidget, 22);
                    
                    // Defer until synchronous workflow restoration has finished. Only one
                    // initialization is allowed, whether this is a new or restored node.
                    const scheduleInitialization = (restoredPromptName = null, restoredPromptText = currentPromptText()) => {
                        clearTimeout(initializationTimer);
                        categoryRequestId++;
                        promptListRequestId++;
                        promptTextRequestId++;
                        suspendPromptNames();
                        initializationTimer = setTimeout(async () => {
                            const isCurrent = await refreshCategories();
                            if (isCurrent && categoryWidget.value) {
                                await loadPrompts(categoryWidget.value, true, restoredPromptName,
                                    currentPromptText() !== restoredPromptText || !!restoredPromptText);
                            }
                        }, 0);
                    };
                    scheduleInitialization();
                    
                    // Let ComfyUI handle widget serialization naturally
                    this.serialize_widgets = true;
                    
                    // Override onConfigure to handle prompt text loading after widget restoration
                    const originalOnConfigure = this.onConfigure;
                    this.onConfigure = function(info) {
                        // Let ComfyUI restore the widget values first
                        if (originalOnConfigure) {
                            originalOnConfigure.call(this, info);
                        }

                        const restoredPromptText = typeof info?.widgets_values?.[2] === "string"
                                ? info.widgets_values[2]
                                : currentPromptText();

                        scheduleInitialization(info?.widgets_values?.[1] ?? promptNameWidget.value, restoredPromptText);
                        this.computeSize();
                        applyCompactLayout();
                        this.setDirtyCanvas(true, true);
                    };
                    
                    // Force the node to resize to show the new buttons
                    this.computeSize();
                    applyCompactLayout();
                    this.setDirtyCanvas(true, true);
                } else {
                    // Could not find required widgets
                }
                
                return r;
            };
        }
    }
});
