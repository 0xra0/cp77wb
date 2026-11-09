-- cp77wb_bridge v0.5.0
-- CET file-RPC companion for cp77wb / Claude Code.
-- Reads retain v1/v2 compatibility. v0.4 mutations retain v2 compatibility.
-- New spatial/transaction mutations require cp77wb-live/3, confirm=true, and
-- World Builder's exact active history singleton.

local bridge = {
    version = "0.5.0",
    protocol = "cp77wb-live/3",
    mutationProtocol = "cp77wb-live/2",
    legacyProtocol = "cp77wb-live/1",
    rpcRoot = "rpc",
    accumulator = 0,
    pollInterval = 0.10
}

local function readJSON(path)
    local file = io.open(path, "r")
    if not file then return nil, "could not open " .. path end
    local raw = file:read("*a")
    file:close()
    local ok, value = pcall(function() return json.decode(raw) end)
    if not ok then return nil, tostring(value) end
    return value, nil
end

local function writeJSON(path, value)
    local file = io.open(path, "w")
    if not file then return false, "could not open " .. path .. " for writing" end
    local ok, encoded = pcall(function() return json.encode(value) end)
    if not ok then
        file:close()
        return false, tostring(encoded)
    end
    file:write(encoded)
    file:close()
    return true, nil
end

local function deepCopy(value)
    return json.decode(json.encode(value))
end

local function vec(v)
    if not v then return nil end
    return { x = v.x or 0, y = v.y or 0, z = v.z or 0, w = v.w or 0 }
end

local function euler(v)
    if not v then return nil end
    return { roll = v.roll or 0, pitch = v.pitch or 0, yaw = v.yaw or 0 }
end

local function getWB()
    local ok, mod = pcall(function() return GetMod("entSpawner") end)
    if not ok then return nil end
    return mod
end

local function getSpawnedUI(wb)
    if not wb or not wb.baseUI or not wb.baseUI.spawnedUI then return nil end
    return wb.baseUI.spawnedUI
end

local function loadedModule(name)
    if package and package.loaded and package.loaded[name] then
        return package.loaded[name]
    end
    local ok, value = pcall(function() return require(name) end)
    if ok then return value end
    return nil
end

-- Only accept World Builder modules that point at the exact same editor state.
local function getSharedHistory(wb)
    local sUI = getSpawnedUI(wb)
    if not sUI then return nil, "World Builder spawnedUI is unavailable" end
    local history = package and package.loaded and package.loaded["modules/utils/history"] or nil
    if not history then history = loadedModule("modules/utils/history") end
    if type(history) ~= "table" then
        return nil, "World Builder history module is not visible in this CET sandbox"
    end
    if history.spawnedUI ~= sUI then
        return nil, "history module is not the World Builder history singleton; live writes disabled"
    end
    if type(history.addAction) ~= "function" or type(history.getElementChange) ~= "function" or type(history.getMultiSelectChange) ~= "function" then
        return nil, "World Builder history API is incompatible"
    end
    return history, nil
end

local function getSharedEditor(wb)
    local sUI = getSpawnedUI(wb)
    if not sUI then return nil, "World Builder spawnedUI is unavailable" end
    -- CET gives each mod its own require cache, so World Builder's editor is only
    -- reachable through the mod object it returns (entSpawner/init.lua: editor = require(...)).
    local editor = (type(wb.editor) == "table" and wb.editor) or loadedModule("modules/utils/editor/editor")
    if type(editor) ~= "table" or editor.spawnedUI ~= sUI then
        return nil, "World Builder editor singleton is unavailable"
    end
    if type(editor.getRaySceneIntersection) ~= "function" then
        return nil, "World Builder editor intersection API is incompatible"
    end
    return editor, nil
end

local function getSharedRegistry(wb)
    local sUI = getSpawnedUI(wb)
    if not sUI then return nil, "World Builder spawnedUI is unavailable" end
    local registry = loadedModule("modules/utils/nodeRefRegistry")
    if type(registry) ~= "table" or registry.spawnedUI ~= sUI then
        return nil, "World Builder NodeRef registry singleton is unavailable"
    end
    if type(registry.update) ~= "function" or type(registry.generate) ~= "function" then
        return nil, "World Builder NodeRef registry API is incompatible"
    end
    return registry, nil
end

local function getSharedConfig()
    local config = loadedModule("modules/utils/config")
    if type(config) ~= "table" or type(config.loadFile) ~= "function" then
        return nil, "World Builder config module is unavailable"
    end
    return config, nil
end

local function historyState(wb)
    local history, err = getSharedHistory(wb)
    if not history then return { available = false, reason = err } end
    return {
        available = true,
        index = history.index or 0,
        actions = history.actions and #history.actions or 0,
        canUndo = (history.index or 0) > 0,
        canRedo = history.actions and (history.index or 0) < #history.actions or false
    }
end

local function requireMutationContext(params)
    if not params or params.confirm ~= true then error("live mutation requires confirm=true") end
    local wb = getWB()
    if not wb then error("World Builder (entSpawner) is not loaded") end
    local sUI = getSpawnedUI(wb)
    if not sUI then error("World Builder spawnedUI is unavailable") end
    local history, err = getSharedHistory(wb)
    if not history then error(err) end
    sUI.cachePaths()
    return wb, sUI, history
end

local function selectedRoots(sUI)
    sUI.cachePaths()
    if #sUI.selectedPaths == 0 then return {} end
    return sUI.getRoots(sUI.selectedPaths)
end

local function refsFromEntries(entries)
    local out = {}
    for _, entry in ipairs(entries) do
        if entry.ref then table.insert(out, entry.ref) end
    end
    return out
end

local function pathsFromRefs(refs)
    local out = {}
    for _, ref in ipairs(refs) do
        local ok, path = pcall(function() return ref:getPath() end)
        table.insert(out, ok and path or ref.name)
    end
    return out
end

local function resetMultiSelectGroup(sUI, refs)
    local group = sUI.multiSelectGroup
    group.childs = refs
    group.origin = nil
    group.rotation = nil
    group.originInitialized = false
    return group
end

local function selectedSummary(sUI)
    sUI.cachePaths()
    local out = {}
    for _, entry in ipairs(sUI.selectedPaths) do
        local ref = entry.ref
        if ref then
            local item = { path = entry.path }
            local okName, name = pcall(function() return ref.name end)
            if okName then item.name = name end
            table.insert(out, item)
        end
    end
    return out
end

local function copyHistoryActions(history)
    local copy = {}
    for i, action in ipairs(history.actions or {}) do copy[i] = action end
    return copy, history.index or 0
end

local function restoreHistoryActions(history, actions, index)
    history.actions = actions
    history.index = index
end

-- Run a transform against existing elements as exactly one WB history action.
-- Internal WB helpers (notably dropToSurface) are allowed to record temporary
-- actions; those are discarded and replaced by the one pre-change snapshot.
local function runChangeTransaction(history, refs, fn)
    local snapshot = history.getMultiSelectChange(refs)
    local actions, index = copyHistoryActions(history)
    local ok, result = pcall(fn)
    restoreHistoryActions(history, actions, index)
    if not ok then
        local rollbackOK, rollbackErr = pcall(function() snapshot.undo() end)
        if not rollbackOK then
            error("operation failed: " .. tostring(result) .. "; rollback also failed: " .. tostring(rollbackErr))
        end
        error(result)
    end
    history.addAction(snapshot)
    return result
end

local function applyMove(sUI, refs, x, y, z)
    local delta = Vector4.new(x or 0, y or 0, z or 0, 0)
    if #refs == 1 then
        refs[1]:setPositionDelta(delta)
    else
        local group = resetMultiSelectGroup(sUI, refs)
        group:setPositionDelta(delta)
        group.childs = {}
    end
end

local function applyRotate(sUI, refs, roll, pitch, yaw)
    local delta = EulerAngles.new(roll or 0, pitch or 0, yaw or 0)
    if #refs == 1 then
        refs[1]:setRotationDelta(delta)
    else
        local group = resetMultiSelectGroup(sUI, refs)
        group:setRotationDelta(delta)
        group.childs = {}
    end
end

local function tablePosition(value)
    if type(value) ~= "table" then return nil end
    return { x = tonumber(value.x) or 0, y = tonumber(value.y) or 0, z = tonumber(value.z) or 0 }
end

local function scalePoint(value, pivot, sx, sy, sz)
    if type(value) ~= "table" then return end
    value.x = pivot.x + ((tonumber(value.x) or 0) - pivot.x) * sx
    value.y = pivot.y + ((tonumber(value.y) or 0) - pivot.y) * sy
    value.z = pivot.z + ((tonumber(value.z) or 0) - pivot.z) * sz
end

local function scaleSerialized(data, pivot, sx, sy, sz, allowPartial, counters)
    if type(data) ~= "table" then return end
    counters = counters or { positions = 0, scales = 0, unsupported = 0 }
    if type(data.spawnable) == "table" then
        if type(data.spawnable.position) == "table" then
            scalePoint(data.spawnable.position, pivot, sx, sy, sz)
            counters.positions = counters.positions + 1
        end
        if type(data.pos) == "table" then scalePoint(data.pos, pivot, sx, sy, sz) end
        if type(data.spawnable.scale) == "table" then
            data.spawnable.scale.x = (tonumber(data.spawnable.scale.x) or 1) * sx
            data.spawnable.scale.y = (tonumber(data.spawnable.scale.y) or 1) * sy
            data.spawnable.scale.z = (tonumber(data.spawnable.scale.z) or 1) * sz
            counters.scales = counters.scales + 1
        else
            counters.unsupported = counters.unsupported + 1
            if not allowPartial then
                error("selection contains an object without spawnable.scale; use allowPartial=true only if repositioning unscaleable objects is intended")
            end
        end
    else
        if type(data.origin) == "table" then
            scalePoint(data.origin, pivot, sx, sy, sz)
            counters.positions = counters.positions + 1
        end
        if type(data.pos) == "table" then scalePoint(data.pos, pivot, sx, sy, sz) end
    end
    for _, child in ipairs(data.childs or {}) do
        scaleSerialized(child, pivot, sx, sy, sz, allowPartial, counters)
    end
    return counters
end

local function selectionPivot(sUI, refs)
    if #refs == 1 then
        local p = refs[1]:getPosition()
        return { x = p.x, y = p.y, z = p.z }
    end
    local group = resetMultiSelectGroup(sUI, refs)
    local p = group:getCenter()
    group.childs = {}
    return { x = p.x, y = p.y, z = p.z }
end

local function applyScale(sUI, refs, params)
    local sx = tonumber(params.x) or 1
    local sy = tonumber(params.y) or 1
    local sz = tonumber(params.z) or 1
    if sx == 0 or sy == 0 or sz == 0 then error("scale factors cannot be zero") end
    local pivot = type(params.pivot) == "table" and tablePosition(params.pivot) or selectionPivot(sUI, refs)
    local counters = { positions = 0, scales = 0, unsupported = 0 }
    for _, ref in ipairs(refs) do
        local data = ref:serialize()
        scaleSerialized(data, pivot, sx, sy, sz, params.allowPartial == true, counters)
        ref:load(data)
    end
    return { factors = { x = sx, y = sy, z = sz }, pivot = pivot, counters = counters }
end

local function directionVector(data, defaultX, defaultY, defaultZ)
    data = type(data) == "table" and data or {}
    local v = Vector4.new(tonumber(data.x) or defaultX, tonumber(data.y) or defaultY, tonumber(data.z) or defaultZ, 0)
    if v.x == 0 and v.y == 0 and v.z == 0 then error("direction cannot be zero") end
    return v:Normalize()
end

local function applySnap(refs, direction)
    for _, ref in ipairs(refs) do
        if type(ref.dropToSurface) ~= "function" then
            error("selected element does not support dropToSurface: " .. tostring(ref.name))
        end
        ref:dropToSurface(false, direction)
    end
end

local NODE_REF_SCALAR_KEYS = { pursuitArea = true, communityRef = true }
local NODE_REF_LIST_KEYS = { workspots = true, spotNodeRefs = true }
local PATH_SCALAR_KEYS = { outlinePath = true }

local function rewriteSpawnableRefs(spawnable, nodeRefs, paths)
    local changed = 0
    local function rewritePath(value)
        if type(value) ~= "string" then return value, false end
        if paths[value] then return paths[value], true end
        for oldPrefix, newPrefix in pairs(paths) do
            if value:sub(1, #oldPrefix + 1) == oldPrefix .. "/" then
                return newPrefix .. value:sub(#oldPrefix + 1), true
            end
        end
        return value, false
    end
    local function walk(value, topLevel)
        if type(value) ~= "table" then return end
        if value["$type"] == "NodeRef" and type(value["$value"]) == "string" and nodeRefs[value["$value"]] then
            value["$value"] = nodeRefs[value["$value"]]
            changed = changed + 1
        end
        for key, child in pairs(value) do
            if topLevel and key == "nodeRef" then
                -- top-level spawnable.nodeRef is a definition, not a reference
            elseif key == "nodeRef" and type(child) == "string" and nodeRefs[child] then
                value[key] = nodeRefs[child]
                changed = changed + 1
            elseif NODE_REF_SCALAR_KEYS[key] and type(child) == "string" and nodeRefs[child] then
                value[key] = nodeRefs[child]
                changed = changed + 1
            elseif PATH_SCALAR_KEYS[key] and type(child) == "string" then
                local newValue, did = rewritePath(child)
                if did then
                    value[key] = newValue
                    changed = changed + 1
                end
            elseif NODE_REF_LIST_KEYS[key] and type(child) == "table" then
                for i, item in ipairs(child) do
                    if type(item) == "string" and nodeRefs[item] then
                        child[i] = nodeRefs[item]
                        changed = changed + 1
                    else
                        walk(item, false)
                    end
                end
            else
                walk(child, false)
            end
        end
    end
    walk(spawnable, true)
    return changed
end

local function rewriteSerializedRefs(data, nodeRefs, paths)
    local changed = 0
    local function walk(node)
        if type(node) ~= "table" then return end
        if type(node.spawnable) == "table" then
            changed = changed + rewriteSpawnableRefs(node.spawnable, nodeRefs, paths)
        end
        for _, child in ipairs(node.childs or {}) do walk(child) end
    end
    walk(data)
    return changed
end

local function collectNodeRefElements(element, out)
    out = out or {}
    if element.spawnable and type(element.spawnable.nodeRef) == "string" and element.spawnable.nodeRef ~= "" then
        table.insert(out, { element = element, old = element.spawnable.nodeRef })
    end
    for _, child in ipairs(element.childs or {}) do collectNodeRefElements(child, out) end
    return out
end

local function remapCloneReferences(wb, clone, oldPath, keepNodeRefs)
    local registry, regErr = getSharedRegistry(wb)
    if not registry and not keepNodeRefs then error(regErr) end
    local newPath = clone:getPath()
    local nodeRefMap = {}
    if not keepNodeRefs then
        -- registry.update() walks spawnedUI.paths, so refresh paths after the clone
        -- was inserted before reserving generated references. This prevents two
        -- clones in the same transaction from receiving the same NodeRef.
        clone.sUI.cachePaths()
        registry.update()
        local seen = {}
        for _, item in ipairs(collectNodeRefElements(clone)) do
            if seen[item.old] then
                error("source subtree contains duplicate NodeRef " .. item.old .. "; repair it before live duplication")
            end
            seen[item.old] = true
            local generated = registry.generate(item.element)
            item.element.spawnable.nodeRef = generated
            nodeRefMap[item.old] = generated
            registry.update()
        end
    end
    local data = clone:serialize()
    rewriteSerializedRefs(data, nodeRefMap, { [oldPath] = newPath })
    clone:load(data)
    if registry then registry.update() end
    return nodeRefMap
end

local function cloneElement(wb, sUI, source, offset, keepNodeRefs)
    local data = deepCopy(source:serialize())
    if data.modulePath == "modules/classes/editor/randomizedGroup" then data.seed = -1 end
    local oldPath = source:getPath()
    local new = require(data.modulePath):new(sUI)
    local ok, result = pcall(function()
        new:load(data)
        new:setParent(source.parent)
        local mapping = remapCloneReferences(wb, new, oldPath, keepNodeRefs)
        if offset and (offset.x ~= 0 or offset.y ~= 0 or offset.z ~= 0) then
            new:setPositionDelta(Vector4.new(offset.x, offset.y, offset.z, 0))
        end
        return mapping
    end)
    if not ok then
        pcall(function() new:remove() end)
        sUI.cachePaths()
        local registry = getSharedRegistry(wb)
        if registry then registry.update() end
        error(result)
    end
    return new, result
end

local function serializeHit(hit)
    if not hit or not hit.hit then return { hit = false } end
    local result = hit.result or {}
    local out = {
        hit = true,
        isNode = hit.isNode == true,
        position = vec(result.position),
        normal = vec(result.normal),
        distance = result.distance,
        collisionType = result.collisionType
    }
    if result.element then
        local ok, path = pcall(function() return result.element:getPath() end)
        if ok then out.path = path end
        out.name = result.element.name
    end
    return out
end

local function lcg(seed)
    local state = math.floor(math.abs(tonumber(seed) or 1)) % 2147483647
    if state == 0 then state = 1 end
    return function()
        state = (state * 48271) % 2147483647
        return state / 2147483647
    end
end

local handlers = {}

handlers.ping = function(_)
    local wb = getWB()
    local hs = wb and historyState(wb) or { available = false, reason = "World Builder is not loaded" }
    local editorOK = false
    local registryOK = false
    if wb then
        editorOK = getSharedEditor(wb) ~= nil
        registryOK = getSharedRegistry(wb) ~= nil
    end
    return {
        bridgeVersion = bridge.version,
        protocol = bridge.protocol,
        supportedProtocols = { bridge.protocol, bridge.mutationProtocol, bridge.legacyProtocol },
        gameLoaded = Game.GetPlayer() ~= nil,
        worldBuilderLoaded = wb ~= nil,
        liveMutation = hs.available,
        history = hs,
        capabilities = {
            read = { "player", "camera", "state", "selection", "paths", "history", "raycast" },
            write = hs.available and { "select", "move", "rotate", "scale", "snap", "batch", "duplicate", "surfaceScatter", "delete", "spawn", "save", "reload", "undo", "redo" } or {},
            sceneIntersection = editorOK,
            referenceAwareDuplicate = registryOK
        }
    }
end

handlers.get_player_transform = function(_)
    local player = Game.GetPlayer()
    if not player then error("player is not available") end
    local result = { position = vec(player:GetWorldPosition()) }
    local ok, transform = pcall(function() return player:GetWorldTransform() end)
    if ok and transform then
        local okRot, rotation = pcall(function() return transform:GetRotation() end)
        if okRot then result.rotation = euler(rotation) end
    end
    return result
end

handlers.get_camera_transform = function(_)
    local player = Game.GetPlayer()
    if not player then error("player is not available") end
    local camera = player:GetFPPCameraComponent()
    if not camera then error("FPP camera component is not available") end
    local transform = camera:GetLocalToWorld()
    return { position = vec(transform:GetTranslation()), rotation = euler(transform:GetRotation()) }
end

handlers.get_worldbuilder_state = function(_)
    local wb = getWB()
    if not wb then error("World Builder (entSpawner) is not loaded") end
    local sUI = getSpawnedUI(wb)
    if sUI then sUI.cachePaths() end
    local selected = sUI and sUI.selectedPaths or {}
    local roots = sUI and sUI.root and sUI.root.childs or {}
    local rootFiles = {}
    for _, ref in ipairs(roots) do
        table.insert(rootFiles, { path = ref:getPath(), name = ref.name, fileName = ref.fileName, supportsSaving = ref.supportsSaving == true })
    end
    return {
        inGame = wb.runtimeData and wb.runtimeData.inGame or false,
        cetOpen = wb.runtimeData and wb.runtimeData.cetOpen or false,
        inMenu = wb.runtimeData and wb.runtimeData.inMenu or false,
        selectionCount = #selected,
        roots = rootFiles,
        history = historyState(wb)
    }
end

handlers.get_worldbuilder_selection = function(params)
    local wb = getWB()
    if not wb then error("World Builder (entSpawner) is not loaded") end
    local sUI = getSpawnedUI(wb)
    if not sUI then error("World Builder spawnedUI is unavailable") end
    sUI.cachePaths()
    local out = {}
    for _, entry in ipairs(sUI.selectedPaths) do
        local ref = entry.ref
        if ref then
            local item = { path = entry.path }
            local okPath, path = pcall(function() return ref:getPath() end)
            if okPath and path ~= nil then item.path = path end
            item.name = ref.name
            item.modulePath = ref.modulePath
            local okPos, position = pcall(function() return ref:getPosition() end)
            if okPos and position then item.position = vec(position) end
            local okRot, rotation = pcall(function() return ref:getRotation() end)
            if okRot and rotation then item.rotation = euler(rotation) end
            local okScale, scale = pcall(function() return ref:getScale() end)
            if okScale and scale then item.scale = vec(scale) end
            item.hasScale = ref.hasScale == true
            if params and params.includeData then
                local okData, data = pcall(function() return ref:serialize() end)
                if okData then item.data = data end
            end
            table.insert(out, item)
        end
    end
    return out
end

handlers.get_history_state = function(_)
    local wb = getWB()
    if not wb then error("World Builder (entSpawner) is not loaded") end
    return historyState(wb)
end

handlers.find_worldbuilder_paths = function(params)
    local wb = getWB()
    if not wb then error("World Builder (entSpawner) is not loaded") end
    local sUI = getSpawnedUI(wb)
    if not sUI then error("World Builder spawnedUI is unavailable") end
    sUI.cachePaths()
    local query = string.lower(tostring(params and params.query or ""))
    local limit = math.max(1, math.min(1000, tonumber(params and params.limit or 100) or 100))
    local out = {}
    for _, entry in ipairs(sUI.paths) do
        local path = tostring(entry.path or "")
        local name = tostring(entry.ref and entry.ref.name or "")
        if query == "" or string.find(string.lower(path), query, 1, true) or string.find(string.lower(name), query, 1, true) then
            table.insert(out, { path = path, name = name, expandable = entry.ref and entry.ref.expandable or false })
            if #out >= limit then break end
        end
    end
    return out
end

handlers.raycast_scene = function(params)
    local wb = getWB()
    if not wb then error("World Builder (entSpawner) is not loaded") end
    local editor, err = getSharedEditor(wb)
    if not editor then error(err) end
    local player = Game.GetPlayer()
    if not player then error("player is not available") end
    local mode = tostring(params.mode or "camera")
    local origin, direction
    if mode == "camera" then
        local camera = player:GetFPPCameraComponent()
        if not camera then error("FPP camera component is not available") end
        local transform = camera:GetLocalToWorld()
        local t = transform:GetTranslation()
        local axis = transform:GetAxisY()
        origin = Vector4.new(t.x, t.y, t.z, 0)
        direction = Vector4.new(axis.x, axis.y, axis.z, 0):Normalize()
    elseif mode == "custom" then
        if type(params.origin) ~= "table" or type(params.direction) ~= "table" then error("custom raycast requires origin and direction") end
        origin = Vector4.new(tonumber(params.origin.x) or 0, tonumber(params.origin.y) or 0, tonumber(params.origin.z) or 0, 0)
        direction = directionVector(params.direction, 0, 0, -1)
    else
        error("unknown raycast mode: " .. mode)
    end
    local hit = editor.getRaySceneIntersection(direction, origin, nil, params.usePhysical ~= false)
    local out = serializeHit(hit)
    out.origin = vec(origin)
    out.direction = vec(direction)
    return out
end

handlers.select_paths = function(params)
    local _, sUI = requireMutationContext(params)
    local paths = params.paths or {}
    if type(paths) ~= "table" then error("paths must be an array") end
    sUI.unselectAll()
    local selected = {}
    for _, path in ipairs(paths) do
        local ref = sUI.getElementByPath(tostring(path))
        if not ref then error("World Builder path not found: " .. tostring(path)) end
        ref:setSelected(true)
        table.insert(selected, ref:getPath())
    end
    sUI.cachePaths()
    return { applied = true, selected = selected }
end

handlers.move_selection = function(params)
    local wb, sUI, history = requireMutationContext(params)
    local refs = refsFromEntries(selectedRoots(sUI))
    if #refs == 0 then error("no World Builder elements are selected") end
    local x, y, z = tonumber(params.x) or 0, tonumber(params.y) or 0, tonumber(params.z) or 0
    runChangeTransaction(history, refs, function() applyMove(sUI, refs, x, y, z) end)
    sUI.cachePaths()
    return { applied = true, changed = #refs, paths = pathsFromRefs(refs), history = historyState(wb) }
end

handlers.rotate_selection = function(params)
    local wb, sUI, history = requireMutationContext(params)
    local refs = refsFromEntries(selectedRoots(sUI))
    if #refs == 0 then error("no World Builder elements are selected") end
    local roll, pitch, yaw = tonumber(params.roll) or 0, tonumber(params.pitch) or 0, tonumber(params.yaw) or 0
    runChangeTransaction(history, refs, function() applyRotate(sUI, refs, roll, pitch, yaw) end)
    sUI.cachePaths()
    return { applied = true, changed = #refs, paths = pathsFromRefs(refs), history = historyState(wb) }
end

handlers.scale_selection = function(params)
    local wb, sUI, history = requireMutationContext(params)
    local refs = refsFromEntries(selectedRoots(sUI))
    if #refs == 0 then error("no World Builder elements are selected") end
    local result = runChangeTransaction(history, refs, function() return applyScale(sUI, refs, params) end)
    sUI.cachePaths()
    result.applied = true
    result.changed = #refs
    result.paths = pathsFromRefs(refs)
    result.history = historyState(wb)
    return result
end

handlers.snap_selection = function(params)
    local wb, sUI, history = requireMutationContext(params)
    local refs = refsFromEntries(selectedRoots(sUI))
    if #refs == 0 then error("no World Builder elements are selected") end
    local direction = directionVector(params.direction, 0, 0, -1)
    runChangeTransaction(history, refs, function() applySnap(refs, direction) end)
    sUI.cachePaths()
    return { applied = true, changed = #refs, paths = pathsFromRefs(refs), direction = vec(direction), history = historyState(wb) }
end

handlers.batch_transform = function(params)
    local wb, sUI, history = requireMutationContext(params)
    local refs = refsFromEntries(selectedRoots(sUI))
    if #refs == 0 then error("no World Builder elements are selected") end
    local operations = params.operations
    if type(operations) ~= "table" or #operations < 1 then error("operations must be a non-empty array") end
    if #operations > 50 then error("batch supports at most 50 operations") end
    local summaries = runChangeTransaction(history, refs, function()
        local out = {}
        for _, op in ipairs(operations) do
            local kind = tostring(op.type or "")
            if kind == "move" then
                applyMove(sUI, refs, tonumber(op.x) or 0, tonumber(op.y) or 0, tonumber(op.z) or 0)
                table.insert(out, { type = kind })
            elseif kind == "rotate" then
                applyRotate(sUI, refs, tonumber(op.roll) or 0, tonumber(op.pitch) or 0, tonumber(op.yaw) or 0)
                table.insert(out, { type = kind })
            elseif kind == "scale" then
                local result = applyScale(sUI, refs, op)
                table.insert(out, { type = kind, result = result })
            elseif kind == "snap" then
                local direction = directionVector(op.direction, 0, 0, -1)
                applySnap(refs, direction)
                table.insert(out, { type = kind, direction = vec(direction) })
            else
                error("unsupported batch operation: " .. kind)
            end
        end
        return out
    end)
    sUI.cachePaths()
    return { applied = true, operations = summaries, changed = #refs, paths = pathsFromRefs(refs), history = historyState(wb) }
end

handlers.duplicate_selection = function(params)
    local wb, sUI, history = requireMutationContext(params)
    local entries = selectedRoots(sUI)
    if #entries == 0 then error("no World Builder elements are selected") end
    local count = math.floor(tonumber(params.count) or 1)
    if count < 1 or count > 500 then error("count must be between 1 and 500") end
    local dx, dy, dz = tonumber(params.x) or 0, tonumber(params.y) or 0, tonumber(params.z) or 0
    local keepNodeRefs = params.keepNodeRefs == true or params.allowDuplicateNodeRefs == true
    local pasted = {}
    local mappings = {}
    sUI.unselectAll()
    local ok, err = pcall(function()
        for copyIndex = 1, count do
            for _, entry in ipairs(entries) do
                local new, mapping = cloneElement(wb, sUI, entry.ref, { x = dx * copyIndex, y = dy * copyIndex, z = dz * copyIndex }, keepNodeRefs)
                new:setSelected(true)
                table.insert(pasted, new)
                table.insert(mappings, mapping)
            end
        end
    end)
    if not ok then
        for _, ref in ipairs(pasted) do pcall(function() ref:remove() end) end
        local registry = getSharedRegistry(wb)
        if registry then registry.update() end
        error(err)
    end
    history.addAction(history.getInsert(pasted))
    sUI.cachePaths()
    return {
        applied = true,
        created = #pasted,
        paths = pathsFromRefs(pasted),
        nodeRefsRemapped = not keepNodeRefs,
        mappings = mappings,
        history = historyState(wb)
    }
end

handlers.surface_scatter = function(params)
    local wb, sUI, history = requireMutationContext(params)
    local entries = selectedRoots(sUI)
    if #entries ~= 1 then error("surface scatter requires exactly one selected root element") end
    local source = entries[1].ref
    local count = math.floor(tonumber(params.count) or 1)
    if count < 1 or count > 500 then error("count must be between 1 and 500") end
    local halfX = math.abs(tonumber(params.halfX) or 5)
    local halfY = math.abs(tonumber(params.halfY) or 5)
    local halfZ = math.abs(tonumber(params.halfZ) or 0)
    local seed = math.floor(tonumber(params.seed) or 1)
    local randomYaw = params.randomYaw ~= false
    local keepNodeRefs = params.keepNodeRefs == true
    local direction = directionVector(params.direction, 0, 0, -1)
    local random = lcg(seed)
    local oldActions, oldIndex = copyHistoryActions(history)
    local pasted = {}
    local ok, err = pcall(function()
        for _ = 1, count do
            local offset = {
                x = (random() * 2 - 1) * halfX,
                y = (random() * 2 - 1) * halfY,
                z = (random() * 2 - 1) * halfZ
            }
            local new = cloneElement(wb, sUI, source, offset, keepNodeRefs)
            table.insert(pasted, new) -- ensure cleanup can remove it if a later spatial operation fails
            if randomYaw then new:setRotationDelta(EulerAngles.new(0, 0, random() * 360)) end
            new:dropToSurface(false, direction)
        end
    end)
    restoreHistoryActions(history, oldActions, oldIndex)
    if not ok then
        for _, ref in ipairs(pasted) do pcall(function() ref:remove() end) end
        local registry = getSharedRegistry(wb)
        if registry then registry.update() end
        error(err)
    end
    sUI.unselectAll()
    for _, ref in ipairs(pasted) do ref:setSelected(true) end
    history.addAction(history.getInsert(pasted))
    sUI.cachePaths()
    return {
        applied = true,
        created = #pasted,
        paths = pathsFromRefs(pasted),
        seed = seed,
        nodeRefsRemapped = not keepNodeRefs,
        direction = vec(direction),
        history = historyState(wb)
    }
end

handlers.delete_selection = function(params)
    local wb, sUI, history = requireMutationContext(params)
    local entries = selectedRoots(sUI)
    if #entries == 0 then error("no World Builder elements are selected") end
    local refs = refsFromEntries(entries)
    local oldPaths = pathsFromRefs(refs)
    history.addAction(history.getRemove(refs))
    sUI.unselectAll()
    for _, ref in ipairs(refs) do ref:remove() end
    local registry = getSharedRegistry(wb)
    if registry then registry.update() end
    sUI.cachePaths()
    return { applied = true, removed = #refs, paths = oldPaths, history = historyState(wb) }
end

handlers.spawn_serialized = function(params)
    local wb, sUI, history = requireMutationContext(params)
    local data = deepCopy(params.data)
    if type(data) ~= "table" or type(data.modulePath) ~= "string" or data.modulePath == "" then error("data.modulePath is required") end
    local parent = sUI.root
    if params.parentPath and params.parentPath ~= "" then
        parent = sUI.getElementByPath(tostring(params.parentPath))
        if not parent then error("parentPath not found: " .. tostring(params.parentPath)) end
        if not parent.expandable then error("parentPath is not an expandable World Builder group") end
    elseif #sUI.selectedPaths == 1 and sUI.selectedPaths[1].ref.expandable then
        parent = sUI.selectedPaths[1].ref
    end

    local placement = tostring(params.placement or "serialized")
    if placement ~= "serialized" then
        if type(data.spawnable) ~= "table" then error("live placement requires spawnable data") end
        local player = Game.GetPlayer()
        if not player then error("player is not available") end
        local camera = player:GetFPPCameraComponent()
        if not camera then error("FPP camera component is not available") end
        local cameraTransform = camera:GetLocalToWorld()
        local cameraRotation = cameraTransform:GetRotation()
        local position
        if placement == "camera" then
            local distance = tonumber(params.distance) or 4.0
            local forward = cameraTransform:GetAxisY()
            local origin = cameraTransform:GetTranslation()
            position = Vector4.new(origin.x + forward.x * distance, origin.y + forward.y * distance, origin.z + forward.z * distance, 0)
        elseif placement == "player" then
            local pp = player:GetWorldPosition()
            position = Vector4.new(pp.x, pp.y, pp.z, 0)
        else
            error("unknown placement: " .. placement)
        end
        local rotation = EulerAngles.new(0, 0, cameraRotation.yaw + 180)
        data.spawnable.position = { x = position.x, y = position.y, z = position.z, w = 0 }
        data.spawnable.rotation = { roll = rotation.roll, pitch = rotation.pitch, yaw = rotation.yaw }
        data.pos = { x = position.x, y = position.y, z = position.z, w = 0 }
    end

    local actions, index = copyHistoryActions(history)
    local new = require(data.modulePath):new(sUI)
    local ok, err = pcall(function()
        new:load(data)
        new:setParent(parent)
        if params.snapToSurface == true then
            new:dropToSurface(false, Vector4.new(0, 0, -1, 0))
        end
    end)
    restoreHistoryActions(history, actions, index)
    if not ok then
        pcall(function() new:remove() end)
        error(err)
    end
    sUI.unselectAll()
    new:setSelected(true)
    history.addAction(history.getInsert({ new }))
    sUI.cachePaths()
    return { applied = true, path = new:getPath(), snapped = params.snapToSurface == true, history = historyState(wb) }
end

handlers.save_roots = function(params)
    local wb, sUI = requireMutationContext(params)
    local saved = {}
    for _, ref in ipairs(sUI.root.childs or {}) do
        if ref.supportsSaving and ref.parent == sUI.root and type(ref.save) == "function" then
            ref:save()
            table.insert(saved, { path = ref:getPath(), fileName = (ref.fileName ~= "" and ref.fileName or ref.name) .. ".json" })
        end
    end
    return { applied = true, saved = saved, count = #saved, history = historyState(wb) }
end

handlers.reload_root = function(params)
    local wb, sUI, history = requireMutationContext(params)
    local path = tostring(params.path or "")
    local old = sUI.getElementByPath(path)
    if not old then error("World Builder path not found: " .. path) end
    if old.parent ~= sUI.root then error("reload_root only supports top-level saved roots") end
    if not old.supportsSaving then error("selected root does not support saving/reload") end
    local config, configErr = getSharedConfig()
    if not config then error(configErr) end
    local fileName = old.fileName ~= "" and old.fileName or old.name
    local data = config.loadFile("data/objects/" .. fileName .. ".json")
    if type(data) ~= "table" or not next(data) then error("saved root file is missing or empty: " .. fileName .. ".json") end
    data.modulePath = data.modulePath or old.modulePath
    local parent = old.parent
    local index = nil
    for i, child in ipairs(parent.childs) do if child == old then index = i break end end
    if not index then error("active root is not present in root child list") end
    local removeAction = history.getRemove({ old })
    old:remove()
    local new = require(data.modulePath):new(sUI)
    local ok, err = pcall(function()
        new:load(data)
        new:setParent(parent, index)
    end)
    if not ok then
        pcall(function() removeAction.undo() end)
        error(err)
    end
    local insertAction = history.getInsert({ new })
    history.addAction({
        undo = function()
            insertAction.undo()
            removeAction.undo()
        end,
        redo = function()
            removeAction.redo()
            insertAction.redo()
        end
    })
    sUI.unselectAll()
    new:setSelected(true)
    sUI.cachePaths()
    local registry = getSharedRegistry(wb)
    if registry then registry.update() end
    return { applied = true, path = new:getPath(), fileName = fileName .. ".json", history = historyState(wb) }
end

handlers.history_undo = function(params)
    local wb, sUI, history = requireMutationContext(params)
    local before = history.index or 0
    history.undo()
    sUI.cachePaths()
    local registry = getSharedRegistry(wb)
    if registry then registry.update() end
    return { applied = (history.index or 0) ~= before, history = historyState(wb), selection = selectedSummary(sUI) }
end

handlers.history_redo = function(params)
    local wb, sUI, history = requireMutationContext(params)
    local before = history.index or 0
    history.redo()
    sUI.cachePaths()
    local registry = getSharedRegistry(wb)
    if registry then registry.update() end
    return { applied = (history.index or 0) ~= before, history = historyState(wb), selection = selectedSummary(sUI) }
end

local v2MutationMethods = {
    select_paths = true,
    move_selection = true,
    rotate_selection = true,
    duplicate_selection = true,
    delete_selection = true,
    spawn_serialized = true,
    history_undo = true,
    history_redo = true
}

local v3MutationMethods = {
    scale_selection = true,
    snap_selection = true,
    batch_transform = true,
    surface_scatter = true,
    save_roots = true,
    reload_root = true
}

local function handleRequest(fileName)
    local reqPath = bridge.rpcRoot .. "/requests/" .. fileName
    local request, err = readJSON(reqPath)
    if not request then
        print("[cp77wb_bridge] Invalid request " .. fileName .. ": " .. tostring(err))
        os.remove(reqPath)
        return
    end
    local id = request.id or fileName:gsub("%.json$", "")
    local response = { id = id, protocol = bridge.protocol, ok = false }
    local p = request.protocol
    local protocolOK = p == bridge.protocol or p == bridge.mutationProtocol or p == bridge.legacyProtocol
    if not protocolOK then
        response.error = "unsupported protocol: " .. tostring(p)
    elseif v3MutationMethods[request.method] and p ~= bridge.protocol then
        response.error = request.method .. " requires " .. bridge.protocol
    elseif v2MutationMethods[request.method] and p == bridge.legacyProtocol then
        response.error = "live mutations require " .. bridge.mutationProtocol .. " or newer"
    elseif not handlers[request.method] then
        response.error = "unknown method: " .. tostring(request.method)
    else
        local ok, result = pcall(handlers[request.method], request.params or {})
        if ok then
            response.ok = true
            response.result = result
        else
            response.error = tostring(result)
        end
    end
    local responsePath = bridge.rpcRoot .. "/responses/" .. tostring(id) .. ".json"
    local wrote, writeErr = writeJSON(responsePath, response)
    if not wrote then print("[cp77wb_bridge] Failed to write response: " .. tostring(writeErr)) end
    os.remove(reqPath)
end

registerForEvent("onInit", function()
    local wb = getWB()
    local hs = wb and historyState(wb) or { available = false }
    print("[cp77wb_bridge] v" .. bridge.version .. " initialized; live mutation=" .. tostring(hs.available))
end)

registerForEvent("onUpdate", function(dt)
    bridge.accumulator = bridge.accumulator + dt
    if bridge.accumulator < bridge.pollInterval then return end
    bridge.accumulator = 0
    local ok, entries = pcall(function() return dir(bridge.rpcRoot .. "/requests") end)
    if not ok or not entries then return end
    for _, file in pairs(entries) do
        if file.type ~= "directory" and file.name:match("^[%w%-_]+%.json$") then handleRequest(file.name) end
    end
end)

return bridge
