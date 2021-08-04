'use strict';

function animate(time) {
    // slide status elements off screen, one by one
    if (ASMDW.statusElements.length != 0) {
        let statusElemInfo = ASMDW.statusElements[0];
        let element = statusElemInfo.element;
        let slideOutStart = statusElemInfo.slideOutStart;
        let slideOutEnd = statusElemInfo.slideOutEnd;
        if (time > slideOutEnd) {
            // remove this element
            element.remove();
            ASMDW.statusElements.shift();
            // make sure the next one starts the disappearing animation now,
            // in case it is disappearing late
            if (ASMDW.statusElements.length != 0) {
                let nextStatusElemInfo = ASMDW.statusElements[0];
                if (nextStatusElemInfo.slideOutStart < time) {
                    nextStatusElemInfo.slideOutStart = time;
                    nextStatusElemInfo.slideOutEnd = time + ASMDW.statusSlideOutDurationMs;
                }
            }
        } else if (time > slideOutStart) {
            // slide this element (and others) up
            let progress = (time - slideOutStart) / (slideOutEnd - slideOutStart);
            let deltaY = -element.offsetHeight * Math.pow(progress, 3);
            statusElemInfo.element.style = 'margin-top: ' + deltaY.toString() + 'px;';
        }
    }
    requestAnimationFrame(animate);
}

function addStatusText(text) {
    // add status text to dom
    let statusElem = document.createElement('div');
    statusElem.appendChild(document.createTextNode(text));
    statusElem.classList.add('status-element');
    ASMDW.dom.statusContainer.appendChild(statusElem);
    // keep track of element for sliding up and removal
    let now = performance.now();
    // todo make status elem disappear time dynamic
    // eg: "Building..." going away when new diff received
    // and "failed to contact server" not going away until next attempt
    ASMDW.statusElements.push({
        element: statusElem,
        slideOutStart: now + 10000,
        slideOutEnd: now + 10000 + ASMDW.statusSlideOutDurationMs,
    });
    return statusElem;
}

// scroll elem1 into view, and elems too if possible
/*
If passed, callback is called before scrolling, if any. (callback may not be called)
Actually scrolling is done only if callback returns true.
callback is passed a boolean indicating if all elements can fit into one view
*/
function scrollIntoView(elem1, elems, callback) {
    let viewportY = window.scrollY;
    let viewportHeight = window.innerHeight;

    let elem1rect = elem1.getBoundingClientRect();
    let elem1y = viewportY + elem1rect.top;
    let elem1height = elem1rect.bottom - elem1rect.top;

    // offset a bit for comfort, use elem heights to avoid hardcoded values
    // offset = 2*average(elem heights)
    // the 2* is because I think it looks better with it
    let offset = elem1height;

    let elemsY = [];
    let elemsHeight = [];
    for (let i = 0; i < elems.length; i++) {
        let elem2 = elems[i];
        let elem2rect = elem2.getBoundingClientRect();
        let elem2y = viewportY + elem2rect.top;
        let elem2height = elem2rect.bottom - elem2rect.top;
        elemsY.push(elem2y);
        elemsHeight.push(elem2height);
        offset += elem2height;
    }

    offset /= (1 + elemsHeight.length);
    offset *= 2;

    // if all elements are reasonably within view (a certain offset from borders)
    // then there's no scrolling to be done at all
    let allElemsWithOffsetInView = true;

    let elem1withOffsetInView = (elem1y - offset) >= viewportY && (elem1y + elem1height + offset) <= (viewportY + viewportHeight);
    if (!elem1withOffsetInView) {
        allElemsWithOffsetInView = false;
    }

    for (let i = 0; i < elems.length; i++) {
        let elem2y = elemsY[i];
        let elem2height = elemsHeight[i];
        let elem2withOffsetInView = (elem2y - offset) >= viewportY && (elem2y + elem2height + offset) <= (viewportY + viewportHeight);
        if (!elem2withOffsetInView) {
            allElemsWithOffsetInView = false;
        }
    }

    if (allElemsWithOffsetInView) {
        return;
    }

    // find min and max Y of elements and associated heights
    let elemMinY = elem1y;
    let elemMinYheight = elem1height;
    let elemMaxY = elem1y;
    let elemMaxYheight = elem1height;
    for (let i = 0; i < elems.length; i++) {
        let elem2y = elemsY[i];
        let elem2height = elemsHeight[i];
        if (elem2y < elemMinY) {
            elemMinY = elem2y;
            elemMinYheight = elem2height;
        }
        if (elem2y > elemMaxY) {
            elemMaxY = elem2y;
            elemMaxYheight = elem2height;
        }
    }

    let allElemsCanBeOnSameView = (elemMaxY + elemMaxYheight - elemMinY) <= viewportHeight;

    if (callback && !callback(allElemsCanBeOnSameView)) {
        return;
    }

    let newViewportY;
    if (allElemsCanBeOnSameView) {
        // scrolling beyond newViewportYmax would put the top of the elemMinY element out of view
        let newViewportYmax = elemMinY;
        // scrolling before newViewportYmin would put the bottom of the elemMaxY element out of view
        let newViewportYmin = elemMaxY + elemMaxYheight - viewportHeight;
        // if currently scrolled below the area we want to scroll to
        if (viewportY >= newViewportYmax) {
            // limit scrolling by scrolling to a point where the area of interest is at the top
            newViewportY = newViewportYmax;
            newViewportY -= offset;
            if (newViewportY < newViewportYmin) {
                // constrained on both directions
                newViewportY = (newViewportYmin + newViewportYmax) / 2;
            }
        } else { // currently scrolled above (or at least, not below) the area we want to scroll to
            // scroll to a point where the area of interest is at the bottom
            newViewportY = newViewportYmin;
            newViewportY += offset;
            if (newViewportY > newViewportYmax) {
                newViewportY = (newViewportYmin + newViewportYmax) / 2;
            }
        }
    } else {
        let newViewportYmax = elem1y;
        let newViewportYmin = elem1y + elem1height - viewportHeight;
        // "ideal" viewport dimensions for showing all elements in one view
        let idealViewportY = elemMinY;
        let idealViewportHeight = elemMaxY + elemMaxYheight - elemMinY;
        // translate the viewport around elem1y according to location of other elements
        newViewportY = elem1y + (idealViewportY - elem1y) / idealViewportHeight * viewportHeight;
        if (newViewportY >= newViewportYmax - offset) {
            newViewportY = newViewportYmax - offset;
        }
        if (newViewportY <= newViewportYmin + offset) {
            newViewportY = newViewportYmin + offset;
        }
    }

    window.scrollTo({
        top: newViewportY,
        behavior: 'smooth',
    });
}

function highlightBranchClearAll() {
    for (let elem of document.getElementsByClassName('branch-indicator-wrapper')) {
        if (elem.classList.contains('ignore')) {
            continue;
        }
        elem.classList.remove('branch-highlight-stay');
        elem.classList.remove('branch-highlight-temp');
    }
}

function highlightBranchStay(className) {
    for (let elem of document.getElementsByClassName(className)) {
        if (elem.classList.contains('ignore')) {
            continue;
        }
        elem.parentNode.classList.add('branch-highlight-stay');
    }
}

function highlightBranchTemp(className) {
    for (let elem of document.getElementsByClassName(className)) {
        if (elem.classList.contains('ignore')) {
            continue;
        }
        elem.parentNode.classList.add('branch-highlight-temp');
    }
}

function highlightBranchTempClear(className) {
    for (let elem of document.getElementsByClassName(className)) {
        if (elem.classList.contains('ignore')) {
            continue;
        }
        elem.parentNode.classList.remove('branch-highlight-temp');
    }
}

// show a popup div at x, y (viewport coordinates)
// for choosing the branch origin to scroll to
function pickOriginBranchOpen(branchOriginsElems, x, y) {
    pickOriginBranchClose();
    let table = document.createElement('table');
    let tbody = document.createElement('tbody');
    table.appendChild(tbody);
    let choices = [];
    for (let branchOriginElem of branchOriginsElems) {
        let tr = document.createElement('tr');
        tbody.appendChild(tr);
        let td = document.createElement('td');
        tr.appendChild(td);
        td.appendChild(document.createTextNode(parseInt(branchOriginElem.dataset.line).toString(16)))
        td.dataset.originBranchPickerIndex = choices.length;
        choices.push(branchOriginElem);
    }
    table.classList.add('origin-branch-picker');
    // magic numbers to offset up and right
    table.style.left = (window.scrollX + x + 15) + 'px';
    table.style.top = (window.scrollY + y - 20) + 'px';
    document.body.appendChild(table);
    ASMDW.originBranchPicker = {
        containerElement: table,
        choices: choices,
    };
}

function pickOriginBranchClick(elem) {
    let choiceIndex = parseInt(elem.dataset.originBranchPickerIndex);
    let branchOriginElem = ASMDW.originBranchPicker.choices[choiceIndex];
    let branchTargetElem = document.getElementById(elem.dataset.branchTarget);
    scrollIntoView(branchOriginElem, branchTargetElem ? [branchTargetElem] : []);
    pickOriginBranchClose();
}

function pickOriginBranchClose() {
    if ('originBranchPicker' in ASMDW) {
        ASMDW.originBranchPicker.containerElement.remove();
    }
}

function onClickBranchOrigin(elem) {
    let branchTargetElem = document.getElementById(elem.dataset.branchTarget);
    if (branchTargetElem) {
        scrollIntoView(branchTargetElem, [elem]);
    }
    highlightBranchClearAll();
    highlightBranchStay(elem.dataset.branchesClass);
}

function onClickBranchTarget(elem, x, y) {
    // get all branch origins that branch to this branch target
    let branchOriginsElems = [];
    for (let branchIndicatorElem of document.getElementsByClassName(elem.dataset.branchesClass)) {
        if (branchIndicatorElem.classList.contains('ignore')) {
            continue;
        }
        if (branchIndicatorElem != elem) {
            branchOriginsElems.push(branchIndicatorElem);
        }
    }

    function callback(allElemsCanBeOnSameView) {
        if (allElemsCanBeOnSameView) {
            return true;
        }
        pickOriginBranchOpen(branchOriginsElems, x, y);
        return false;
    }
    if (branchOriginsElems.length == 1) {
        scrollIntoView(branchOriginsElems[0], elem);
    } else {
        // main element doesn't matter, either everything will be in one view,
        // or the origin branch picker will show up and no scrolling happens
        scrollIntoView(elem, branchOriginsElems, callback);
    }

    highlightBranchClearAll();
    highlightBranchStay(elem.dataset.branchesClass);
}

function onMouseEnterBranchIndicator(ev) {
    highlightBranchTemp(ev.target.dataset.branchesClass);
}

function onMouseLeaveBranchIndicator(ev) {
    highlightBranchTempClear(ev.target.dataset.branchesClass);
}

function updateObjectNamesDataList() {
    let objectNamesDataListElem = ASMDW.dom.objectNamesDataList;
    while (objectNamesDataListElem.firstChild) {
        objectNamesDataListElem.firstChild.remove();
    }
    for (let objname in ASMDW.mapFileDump.byObject) {
        let dataListOptionElem = document.createElement('option');
        dataListOptionElem.value = objname;
        objectNamesDataListElem.appendChild(dataListOptionElem);
    }
}

function updateFunctionNamesDataList() {
    let functionNamesDataListElem = ASMDW.dom.functionNamesDataList;
    while (functionNamesDataListElem.firstChild) {
        functionNamesDataListElem.firstChild.remove();
    }
    if (ASMDW.dom.onlyShowFunctionsFromObjectCheckbox.checked) {
        let targetObjname = ASMDW.dom.targetObjectInput.value;
        if (targetObjname in ASMDW.mapFileDump.byObject) {
            let objectFunctions = ASMDW.mapFileDump.byObject[targetObjname];
            for (let funcInfo of objectFunctions) {
                let dataListOptionElem = document.createElement('option');
                dataListOptionElem.value = funcInfo.fn_name;
                functionNamesDataListElem.appendChild(dataListOptionElem);
            }
        }
    } else {
        for (let fn_name in ASMDW.mapFileDump.byFunction) {
            let dataListOptionElem = document.createElement('option');
            dataListOptionElem.value = fn_name;
            functionNamesDataListElem.appendChild(dataListOptionElem);
        }
    }
}

function parseMapFileDump(contents) {
    let lines = contents.split('\n');
    let mapFileDumpByFunction = {};
    let mapFileDumpByObject = {};
    for (let line of lines) {
        if (line == '') {
            continue;
        }
        let parts = line.split(' ', 4);
        let fn_name = parts[0];
        let ram = parseInt(parts[1], 16);
        let rom = parseInt(parts[2], 16);
        let objname = parts[3];
        let lastPathSeparatorIdx = Math.max(objname.lastIndexOf('/'), objname.lastIndexOf('\\'));
        if (lastPathSeparatorIdx >= 0) {
            objname = objname.substr(lastPathSeparatorIdx + 1);
        }
        mapFileDumpByFunction[fn_name] = { ram, rom, objname };
        if (!(objname in mapFileDumpByObject)) {
            mapFileDumpByObject[objname] = [];
        }
        mapFileDumpByObject[objname].push({ fn_name, ram, rom, objname });
    }
    ASMDW.mapFileDump = {
        byFunction: mapFileDumpByFunction,
        byObject: mapFileDumpByObject,
    };
}

function onMapFileDumpRequestStatusChange(httpRequest) {
    if (httpRequest.readyState == XMLHttpRequest.DONE) {
        if (httpRequest.status == 200) { // OK
            parseMapFileDump(httpRequest.responseText);
            updateObjectNamesDataList();
            updateFunctionNamesDataList();
        } else if (httpRequest.status == 404) {
            // no linker map file set in diff_settings.py
        } else { // error
            addStatusText('Could not fetch the linker map file');
        }
        onMapFileDumpFinished();
    }
}

function requestLinkerMapFileDump() {
    let httpRequest = new XMLHttpRequest();
    httpRequest.onreadystatechange = function () {
        onMapFileDumpRequestStatusChange(httpRequest);
    };
    let url = '?linkermap';
    httpRequest.open('GET', url);
    httpRequest.send();
}

function onMapFileDumpFinished() {
    if (ASMDW.info !== null) {
        onMapFileDumpAndGetInfoFinished();
    }
}

function onGetInfoFinished() {
    if (ASMDW.mapFileDump !== null) {
        onMapFileDumpAndGetInfoFinished();
    }
}

function onMapFileDumpAndGetInfoFinished() {
    let start = ASMDW.info.start;
    if (start in ASMDW.mapFileDump.byFunction) {
        let funcInfo = ASMDW.mapFileDump.byFunction[start];
        ASMDW.dom.targetObjectInput.value = funcInfo.objname;
        updateFunctionNamesDataList();
        ASMDW.dom.targetFunctionInput.value = start;
    } else {
        console.log(start, 'not in mapFileDump.byFunction (TODO)')
    }
}

function onInfoRequestStatusChange(httpRequest) {
    if (httpRequest.readyState == XMLHttpRequest.DONE) {
        if (httpRequest.status == 200) { // OK
            let info = {};
            let lines = httpRequest.responseText.split('\n');
            for (let line of lines) {
                if (line == '') {
                    continue;
                }
                let parts = line.split(' ', 2);
                if (parts.length != 2) {
                    console.warn('Could not split info line into two parts:', line)
                    continue;
                }
                info[parts[0]] = parts[1];
            }
            ASMDW.info = info;
        } else { // error
            addStatusText('Could not fetch info');
        }
    }
}

function requestInfo() {
    let httpRequest = new XMLHttpRequest();
    httpRequest.onreadystatechange = function () {
        onInfoRequestStatusChange(httpRequest);
    };
    let url = '?info';
    httpRequest.open('GET', url);
    httpRequest.send();
}

function setDiffHtml(diffHtml) {
    ASMDW.dom.diffContainer.innerHTML = diffHtml;
    // looking for branch indicator elements
    // in first and second columns, find span-wrapped span elements
    for (let span of ASMDW.dom.diffContainer.querySelectorAll('tbody > tr > td:not(:nth-child(3)) > span > span')) {
        if ('branchesClass' in span.dataset) {
            span.addEventListener('mouseenter', onMouseEnterBranchIndicator);
            span.addEventListener('mouseleave', onMouseLeaveBranchIndicator);
        }
    }
    for (let span of ASMDW.dom.diffContainer.querySelectorAll('tbody > tr > td:nth-child(3) > span > span')) {
        if ('branchesClass' in span.dataset) {
            span.classList.add('ignore');
        }
    }
}

function onNewContent() {
    let httpRequest = ASMDW.httpRequest;
    if (httpRequest.readyState == XMLHttpRequest.DONE) {
        if (httpRequest.status == 200) { // OK
            ASMDW.tryAgainAfterCommunicationFailureDelayMs = 0;
            let res = httpRequest.responseText;
            let resInfoEndIdx = res.indexOf('\n');
            let resInfo = res.slice(0, resInfoEndIdx);
            let nextRequestDelay = 100;
            switch (resInfo) {
                case 'refresh':
                    nextRequestDelay = 0;
                    break;
                case 'diff':
                case 'diff once':
                    ASMDW.diffReceived++;
                    let resDiffHtml = res.slice(resInfoEndIdx + 1);
                    setDiffHtml(resDiffHtml);
                    break;
                case 'status':
                    let resStatusText = res.slice(resInfoEndIdx + 1);
                    addStatusText(resStatusText);
                    break;
                default:
                    alert('Unknown resInfo = ' + resInfo);
                    nextRequestDelay = 5000;
            }
            if (resInfo != 'diff once') {
                if (nextRequestDelay > 0) {
                    ASMDW.requestContentTimeoutID = setTimeout(requestContent, nextRequestDelay);
                } else {
                    requestContent();
                }
            }
        } else {
            if (ASMDW.tryAgainAfterCommunicationFailureDelayMs == 0) {
                ASMDW.tryAgainAfterCommunicationFailureDelayMs = 5000;
            } else {
                ASMDW.tryAgainAfterCommunicationFailureDelayMs *= 2;
            }
            let statusElem = addStatusText(
                'Failed to communicate with server, trying again in '
                + Math.round(ASMDW.tryAgainAfterCommunicationFailureDelayMs / 1000).toString()
                + ' seconds'
            );
            let retryNow = document.createElement('span');
            retryNow.appendChild(document.createTextNode('(retry now)'));
            retryNow.classList.add('communication-error-retry-now');
            retryNow.addEventListener('click', function (ev) {
                let retryNow = ev.target;
                retryNow.remove();
                requestContent();
            });
            statusElem.appendChild(document.createTextNode(' '));
            statusElem.appendChild(retryNow);
            ASMDW.requestContentTimeoutID = setTimeout(requestContent, ASMDW.tryAgainAfterCommunicationFailureDelayMs);
        }
    }
}

function requestContent() {
    if (ASMDW.requestContentTimeoutID !== null) {
        clearTimeout(ASMDW.requestContentTimeoutID);
        ASMDW.requestContentTimeoutID = null;
    }
    let httpRequest = new XMLHttpRequest();
    ASMDW.httpRequest = httpRequest;
    httpRequest.onreadystatechange = onNewContent;
    let url = '?diff';
    if (ASMDW.diffReceived == 0)
        url += "&nowait";
    httpRequest.open('GET', url);
    httpRequest.send();
}

function onTargetFunctionChange() {
    let httpRequest = new XMLHttpRequest();
    let url = '?set&start=' + encodeURIComponent(ASMDW.dom.targetFunctionInput.value);
    httpRequest.open('GET', url);
    httpRequest.send();
}

function onClick(ev) {
    let elem = ev.target;
    if (elem.classList.contains('ignore')) {
        return;
    }
    let x = ev.clientX;
    let y = ev.clientY;
    pickOriginBranchClose();
    if (elem.classList.contains('branch-indicator')) {
        // branch origins have data-branch-target
        if ('branchTarget' in elem.dataset) {
            onClickBranchOrigin(elem);
        } else {
            onClickBranchTarget(elem, x, y);
        }
    } else if ('originBranchPickerIndex' in elem.dataset) {
        pickOriginBranchClick(elem);
    } else {
        highlightBranchClearAll();
    }
}

function onBodyLoaded() {
    ASMDW.dom = {
        diffContainer: document.getElementById('diff-container'),
        statusContainer: document.getElementById('status-container'),
        targetObjectInput: document.getElementById('target-object'),
        targetFunctionInput: document.getElementById('target-function'),
        onlyShowFunctionsFromObjectCheckbox: document.getElementById('only-functions-from-object'),
        objectNamesDataList: document.getElementById('object-names'),
        functionNamesDataList: document.getElementById('function-names'),
    };
    requestContent();
    requestLinkerMapFileDump();
    requestInfo();
    document.body.addEventListener('click', onClick);
    ASMDW.dom.targetObjectInput.addEventListener('change', updateFunctionNamesDataList);
    ASMDW.dom.onlyShowFunctionsFromObjectCheckbox.addEventListener('change', updateFunctionNamesDataList);
    ASMDW.dom.targetFunctionInput.addEventListener('change', onTargetFunctionChange);
    requestAnimationFrame(animate);

}

// asm-differ web
window.ASMDW = {
    requestContentTimeoutID: null,
    diffReceived: 0,
    tryAgainAfterCommunicationFailureDelayMs: 0,
    statusSlideOutDurationMs: 500,
    statusElements: [],
    mapFileDump: null,
    info: null,
};
