/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SearchModel } from "@web/search/search_model";
import { userService } from "@web/core/user_service";
import { Domain } from "@web/core/domain";

patch(userService, "cr_advance_search_more.userService", {
    start(env) {
        const result = this._super(...arguments);
        const mode = window.sessionStorage.getItem("cr_advance_search_mode") || "default";
        result.updateContext({ cr_search_mode: mode });
        return result;
    },
});

patch(SearchModel.prototype, "cr_advance_search_more.SearchModel", {
    setup() {
        this._super(...arguments);
        this.searchMode = window.sessionStorage.getItem("cr_advance_search_mode") || "default";
        this.columnFilters = {};
        if (this.userService) {
            this.userService.updateContext({ cr_search_mode: this.searchMode });
        }
        if (this.globalContext) {
            this.globalContext.cr_search_mode = this.searchMode;
        }
    },

    async load(config) {
        const result = await this._super(...arguments);
        const mode = this.searchMode || window.sessionStorage.getItem("cr_advance_search_mode") || "default";
        this.searchMode = mode;
        if (this.globalContext) {
            this.globalContext.cr_search_mode = mode;
        }
        if (this.userService) {
            this.userService.updateContext({ cr_search_mode: mode });
        }
        return result;
    },

    async reload(config = {}) {
        const result = await this._super(...arguments);
        const mode = this.searchMode || window.sessionStorage.getItem("cr_advance_search_mode") || "default";
        if (this.globalContext) {
            this.globalContext.cr_search_mode = mode;
        }
        if (this.userService) {
            this.userService.updateContext({ cr_search_mode: mode });
        }
        return result;
    },

    _clearParams() {
        if (this._super) {
            this._super(...arguments);
        }
        this.columnFilters = {};
    },

    setSearchMode(mode) {
        console.log("[CR_SEARCH] SearchModel setSearchMode:", mode);
        this.searchMode = mode;
        window.sessionStorage.setItem("cr_advance_search_mode", mode);
        if (this.userService) {
            this.userService.updateContext({ cr_search_mode: mode });
        }
        if (this.globalContext) {
            this.globalContext.cr_search_mode = mode;
        }
        this._notify();
    },

    setColumnFilter(fieldName, filterData) {
        if (!this.columnFilters) {
            this.columnFilters = {};
        }
        if (filterData === null || filterData === undefined || filterData === "" || (Array.isArray(filterData) && filterData.length === 0)) {
            delete this.columnFilters[fieldName];
        } else {
            this.columnFilters[fieldName] = filterData;
        }
        this._notify();
    },

    clearColumnFilters() {
        this.columnFilters = {};
        this._notify();
    },

    getColumnFiltersDomain() {
        if (!this.columnFilters || Object.keys(this.columnFilters).length === 0) {
            return [];
        }
        const domain = [];
        for (const [field, data] of Object.entries(this.columnFilters)) {
            if (!data) continue;
            const fieldDef = this.resModelFields?.[field];
            if (fieldDef) {
                if (fieldDef.searchable === false) continue;
                if (["binary", "properties", "json", "html"].includes(fieldDef.type)) continue;

                if (fieldDef.type === "boolean" && Array.isArray(data)) {
                    const hasTrue = data.includes("true");
                    const hasFalse = data.includes("false");
                    if (hasTrue && !hasFalse) {
                        domain.push([field, "=", true]);
                    } else if (hasFalse && !hasTrue) {
                        domain.push([field, "=", false]);
                    }
                    continue;
                }
            }
            if (typeof data === "string" || typeof data === "number") {
                const valStr = String(data).trim();
                if (valStr) {
                    domain.push([field, "ilike", valStr]);
                }
            } else if (Array.isArray(data)) {
                if (data.length > 0) {
                    domain.push([field, "in", data]);
                }
            } else if (typeof data === "object") {
                if (data.start) {
                    domain.push([field, ">=", data.start]);
                }
                if (data.end) {
                    domain.push([field, "<=", data.end]);
                }
            }
        }
        return domain;
    },

    getActiveSearchKeywords() {
        const keywords = new Set();

        if (this.columnFilters) {
            for (const val of Object.values(this.columnFilters)) {
                if (typeof val === "string" || typeof val === "number") {
                    const str = String(val).trim();
                    if (str.length >= 1) {
                        const words = str.split(/\s+/).filter(Boolean);
                        words.forEach((w) => {
                            if (w.length >= 1) keywords.add(w);
                        });
                    }
                }
            }
        }

        if (Array.isArray(this.facets)) {
            for (const facet of this.facets) {
                if (facet.values) {
                    const vals = Array.isArray(facet.values) ? facet.values : [facet.values];
                    for (const v of vals) {
                        if (typeof v === "string" && v.trim()) {
                            const words = v.trim().split(/\s+/).filter(Boolean);
                            words.forEach((w) => {
                                if (w.length >= 1) keywords.add(w);
                            });
                        }
                    }
                }
            }
        }

        const currentDomain = this.domain;
        if (Array.isArray(currentDomain)) {
            for (const leaf of currentDomain) {
                if (Array.isArray(leaf) && leaf.length === 3) {
                    const [field, op, val] = leaf;
                    if (typeof val === "string" && val.trim() && ["ilike", "=ilike", "like", "="].includes(op)) {
                        const words = val.trim().split(/\s+/).filter(Boolean);
                        words.forEach((w) => {
                            if (w.length >= 1) keywords.add(w);
                        });
                    }
                }
            }
        }

        return Array.from(keywords);
    },

    saveSearchHistory(query, mode) {
        if (!query || typeof query !== "string" || !query.trim() || !this.resModel) return;
        const cleanQuery = query.trim();
        const key = `cr_recent_history_${this.resModel}`;
        try {
            const raw = window.localStorage.getItem(key);
            let items = raw ? JSON.parse(raw) : [];
            items = items.filter((item) => item.query.toLowerCase() !== cleanQuery.toLowerCase());
            items.unshift({
                id: Date.now() + Math.random(),
                query: cleanQuery,
                mode: mode || this.searchMode || "default",
                timestamp: new Date().toISOString(),
            });
            if (items.length > 15) {
                items = items.slice(0, 15);
            }
            window.localStorage.setItem(key, JSON.stringify(items));
        } catch (e) {
            // ignore localStorage errors
        }
    },

    saveCustomFilterHistory(domain, mode, filterName) {
        if (!domain || !this.resModel) return;
        const key = `cr_saved_filters_${this.resModel}`;
        try {
            const raw = window.localStorage.getItem(key);
            let items = raw ? JSON.parse(raw) : [];

            let name = filterName;
            if (!name) {
                if (typeof domain === "string") {
                    name = domain;
                } else if (Array.isArray(domain)) {
                    name = domain.map((leaf) => (Array.isArray(leaf) ? leaf.join(" ") : String(leaf))).join(" & ");
                } else {
                    name = "Custom Filter";
                }
            }
            if (name.length > 50) {
                name = name.substring(0, 47) + "...";
            }

            const targetDomain = typeof domain === "string" ? domain : JSON.stringify(domain);
            const targetMode = mode || this.searchMode || "default";

            // Deduplicate by exact domain match OR name match
            const existingIndex = items.findIndex(
                (item) => (item.domain === targetDomain || item.name.toLowerCase() === name.toLowerCase()) && item.mode === targetMode
            );

            let finalName = name;
            let finalId = Date.now() + Math.random();

            if (existingIndex >= 0) {
                const existingItem = items[existingIndex];
                finalName = existingItem.name || name;
                finalId = existingItem.id;
                items.splice(existingIndex, 1);
            }

            items.unshift({
                id: finalId,
                name: finalName,
                domain: targetDomain,
                mode: targetMode,
                timestamp: new Date().toISOString(),
            });

            if (items.length > 15) {
                items = items.slice(0, 15);
            }
            window.localStorage.setItem(key, JSON.stringify(items));
        } catch (e) {
            // ignore localStorage errors
        }
    },

    saveCustomGroupByHistory(groupByFields, mode, groupByName) {
        if (!groupByFields || !this.resModel) return;
        const key = `cr_saved_groupby_${this.resModel}`;
        try {
            const raw = window.localStorage.getItem(key);
            let items = raw ? JSON.parse(raw) : [];

            let fieldsArr = Array.isArray(groupByFields) ? groupByFields : [groupByFields];
            let name = groupByName || fieldsArr.join(", ");
            if (!name || typeof name !== "string") {
                name = fieldsArr.join(", ");
            }
            if (name.length > 50) {
                name = name.substring(0, 47) + "...";
            }

            const targetGroupKey = JSON.stringify(fieldsArr);
            const targetMode = mode || "GROUP";

            // Deduplicate by exact groupBy structure or name
            const existingIndex = items.findIndex(
                (item) => (JSON.stringify(item.groupBy) === targetGroupKey || item.name.toLowerCase() === name.toLowerCase())
            );

            let finalName = name;
            let finalId = Date.now() + Math.random();

            if (existingIndex >= 0) {
                const existingItem = items[existingIndex];
                finalName = existingItem.name || name;
                finalId = existingItem.id;
                items.splice(existingIndex, 1);
            }

            items.unshift({
                id: finalId,
                name: finalName,
                groupBy: fieldsArr,
                mode: targetMode,
                timestamp: new Date().toISOString(),
            });

            if (items.length > 15) {
                items = items.slice(0, 15);
            }
            window.localStorage.setItem(key, JSON.stringify(items));
        } catch (e) {
            // ignore localStorage errors
        }
    },

    async applyGroupBy(groupByFields) {
        if (!this.resModel || !groupByFields) return;
        let fields = groupByFields;
        if (typeof fields === "string") {
            try {
                fields = JSON.parse(fields);
            } catch (e) {
                fields = [fields];
            }
        }
        if (!Array.isArray(fields)) {
            fields = [fields];
        }

        const searchItems = Object.values(this.searchItems || {});

        for (const fieldSpec of fields) {
            if (!fieldSpec) continue;
            const existingItem = searchItems.find((si) =>
                si.type === "groupBy" &&
                (si.fieldName === fieldSpec || si.name === fieldSpec || (si.fieldName && fieldSpec.startsWith(si.fieldName)))
            );

            if (existingItem) {
                const isActive = this.query.some((q) => q.searchItemId === existingItem.id);
                if (!isActive) {
                    this.toggleSearchItem(existingItem.id);
                }
            } else {
                if (typeof this.createNewGroupBy === "function") {
                    await this.createNewGroupBy(fieldSpec);
                } else if (typeof this.toggleGroupBy === "function") {
                    await this.toggleGroupBy(fieldSpec);
                }
            }
        }
    },

    createNewGroupBy(fieldName) {
        const result = this._super ? this._super(...arguments) : null;
        try {
            if (fieldName) {
                this.saveCustomGroupByHistory([fieldName], "GROUP", fieldName);
            }
        } catch (e) {}
        return result;
    },

    toggleSearchItem(searchItemId) {
        const result = this._super(...arguments);
        try {
            const item = this.searchItems ? this.searchItems[searchItemId] : null;
            const isActive = this.query.some((q) => q.searchItemId === searchItemId);
            if (item && item.type === "groupBy" && isActive) {
                const fieldName = item.fieldName || item.name || item.description;
                const displayName = item.description || item.name || fieldName;
                if (fieldName) {
                    this.saveCustomGroupByHistory([fieldName], "GROUP", displayName);
                }
            }
        } catch (e) {}
        return result;
    },

    createNewFilters(prefilters) {
        const result = this._super ? this._super(...arguments) : null;
        try {
            if (Array.isArray(prefilters)) {
                for (const preFilter of prefilters) {
                    this.saveCustomFilterHistory(
                        preFilter.domain,
                        this.searchMode || "default",
                        preFilter.description
                    );
                }
            }
        } catch (e) {
            // ignore
        }
        return result;
    },

    async splitAndAddDomain(domain, description) {
        const domainStr = typeof domain === "string" ? domain : new Domain(domain).toString();
        let desc = description;
        if (!desc) {
            if (typeof domain === "string") {
                desc = domain;
            } else if (Array.isArray(domain)) {
                desc = domain.map((leaf) => (Array.isArray(leaf) ? leaf.join(" ") : String(leaf))).join(" & ");
            } else {
                desc = "Custom Filter";
            }
        }
        this.createNewFilters([
            {
                description: desc,
                domain: domainStr,
                type: "filter",
            },
        ]);
    },

    addAutoCompletionValues(searchItemId, autocompleteValue) {
        this._super(...arguments);
        if (autocompleteValue) {
            let queryVal = "";
            if (typeof autocompleteValue.value === "string" && autocompleteValue.value.trim()) {
                queryVal = autocompleteValue.value;
            } else if (typeof autocompleteValue.label === "string" && autocompleteValue.label.trim()) {
                queryVal = autocompleteValue.label;
            }
            if (queryVal && queryVal.trim()) {
                this.saveSearchHistory(queryVal.trim(), this.searchMode || "default");
            }
        }
    },

    _transformDomainLeaf(leaf, mode) {
        if (!Array.isArray(leaf) || leaf.length !== 3) {
            return [leaf];
        }
        const [field, operator, val] = leaf;
        if (
            typeof val !== "string" ||
            !val.trim() ||
            !["ilike", "=ilike", "like", "=", "child_of", "parent_of"].includes(operator)
        ) {
            return [leaf];
        }

        const keywords = val.trim().split(/\s+/).filter(Boolean);
        if (keywords.length <= 1) {
            return [leaf];
        }

        let result = [leaf];
        if (mode === "or") {
            const orDomain = [];
            for (let i = 0; i < keywords.length - 1; i++) {
                orDomain.push("|");
            }
            for (const keyword of keywords) {
                orDomain.push([field, operator, keyword]);
            }
            result = orDomain;
        } else if (mode === "and") {
            const andDomain = [];
            for (let i = 0; i < keywords.length - 1; i++) {
                andDomain.push("&");
            }
            for (const keyword of keywords) {
                andDomain.push([field, operator, keyword]);
            }
            result = andDomain;
        }

        console.log("[CR_SEARCH] SearchModel _transformDomainLeaf:", {
            field,
            operator,
            val,
            mode,
            keywords,
            result,
        });
        return result;
    },

    _processDomainForSearchMode(domain, mode) {
        if (!domain || !domain.length || mode === "default") {
            return domain;
        }

        if (mode === "not") {
            const domainForOr = this._processDomainForSearchMode(domain, "or");
            const notDomain = ["!", ...domainForOr];
            console.log("[CR_SEARCH] SearchModel _processDomainForSearchMode NOT mode:", {
                original: domain,
                result: notDomain,
            });
            return notDomain;
        }

        const resultDomain = [];
        for (const item of domain) {
            if (Array.isArray(item) && item.length === 3) {
                const transformed = this._transformDomainLeaf(item, mode);
                resultDomain.push(...transformed);
            } else {
                resultDomain.push(item);
            }
        }
        return resultDomain;
    },

    _getSearchItemDomain(activeItem, options = {}) {
        const domain = this._super ? this._super(...arguments) : null;
        if (!domain) {
            return domain;
        }
        const { searchItemId } = activeItem;
        const searchItem = this.searchItems[searchItemId];
        // Only apply Search Mode (OR, AND, NOT) to user-typed search bar fields, preserving view filters and action domains!
        if (searchItem && ["field", "field_property"].includes(searchItem.type)) {
            const mode = this.searchMode || "default";
            if (mode !== "default") {
                let domainArray = [];
                try {
                    const evalContext = Object.assign(
                        {},
                        this.globalContext,
                        this.userService?.context || {}
                    );
                    domainArray = Array.isArray(domain) ? domain : domain.toList(evalContext);
                } catch (e) {
                    domainArray = Array.isArray(domain) ? domain : [];
                }
                const processed = this._processDomainForSearchMode(domainArray, mode);
                console.log("[CR_SEARCH] SearchModel _getSearchItemDomain:", {
                    searchItem: searchItem.description || searchItem.name,
                    mode,
                    original: domainArray,
                    processed,
                });
                return new Domain(processed);
            }
        }
        return domain;
    },

    get domain() {
        const baseDomain = this._super();
        const colDomain = this.getColumnFiltersDomain();
        const finalDomain = colDomain.length > 0 ? [...baseDomain, ...colDomain] : baseDomain;
        console.log("[CR_SEARCH] SearchModel get domain():", {
            activeMode: this.searchMode || "default",
            baseDomain: JSON.parse(JSON.stringify(baseDomain || [])),
            finalDomain: JSON.parse(JSON.stringify(finalDomain || [])),
        });
        return finalDomain;
    },
    set domain(v) {},

    get context() {
        const ctx = this._super();
        const resultCtx = Object.assign({}, ctx, {
            cr_search_mode: this.searchMode || "default",
        });
        return resultCtx;
    },
    set context(v) {},
});
