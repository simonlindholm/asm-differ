'use strict';

function animate(time) {
    // slide status elements off screen, one by one
    if (ASMDW.statusElements.length != 0) {
        var statusElemInfo = ASMDW.statusElements[0];
        var element = statusElemInfo.element;
        var slideOutStart = statusElemInfo.slideOutStart;
        var slideOutEnd = statusElemInfo.slideOutEnd;
        if (time > slideOutEnd) {
            // remove this element
            element.remove();
            ASMDW.statusElements.shift();
            // make sure the next one starts the disappearing animation now,
            // in case it is disappearing late
            if (ASMDW.statusElements.length != 0) {
                var nextStatusElemInfo = ASMDW.statusElements[0];
                if (nextStatusElemInfo.slideOutStart < time) {
                    nextStatusElemInfo.slideOutStart = time;
                    nextStatusElemInfo.slideOutEnd = time + ASMDW.statusSlideOutDurationMs;
                }
            }
        } else if (time > slideOutStart) {
            // slide this element (and others) up
            var progress = (time - slideOutStart) / (slideOutEnd - slideOutStart);
            var deltaY = -element.offsetHeight * Math.pow(progress, 3);
            statusElemInfo.element.style = 'margin-top: ' + deltaY.toString() + 'px;';
        }
    }
    requestAnimationFrame(animate);
}

function addStatusText(text) {
    // add status text to dom
    var statusElem = document.createElement('div');
    statusElem.appendChild(document.createTextNode(text));
    statusElem.classList.add('status-element');
    ASMDW.dom.statusContainer.appendChild(statusElem);
    // keep track of element for sliding up and removal
    var now = performance.now();
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
function scrollIntoView(elem1, elems) {
    var viewportY = window.scrollY;
    var viewportHeight = window.innerHeight;

    var elem1rect = elem1.getBoundingClientRect();
    var elem1y = viewportY + elem1rect.top;
    var elem1height = elem1rect.bottom - elem1rect.top;

    // offset a bit for comfort, use elem heights to avoid hardcoded values
    var offset = elem1height;

    var elemsY = [];
    var elemsHeight = [];
    for (var i = 0; i < elems.length; i++) {
        var elem2 = elems[i];
        var elem2rect = elem2.getBoundingClientRect();
        var elem2y = viewportY + elem2rect.top;
        var elem2height = elem2rect.bottom - elem2rect.top;
        elemsY.push(elem2y);
        elemsHeight.push(elem2height);
        offset += elem2height;
    }

    offset /= (1 + elemsHeight.length);
    offset *= 2;

    var allElemsWithOffsetInView = true;

    var elem1withOffsetInView = (elem1y - offset) >= viewportY && (elem1y + elem1height + offset) <= (viewportY + viewportHeight);
    if (!elem1withOffsetInView) {
        allElemsWithOffsetInView = false;
    }

    for (var i = 0; i < elems.length; i++) {
        var elem2y = elemsY[i];
        var elem2height = elemsHeight[i];
        var elem2withOffsetInView = (elem2y - offset) >= viewportY && (elem2y + elem2height + offset) <= (viewportY + viewportHeight);
        if (!elem2withOffsetInView) {
            allElemsWithOffsetInView = false;
        }
    }

    if (allElemsWithOffsetInView) {
        return;
    }

    var elemMinY = elem1y;
    var elemMinYheight = elem1height;
    var elemMaxY = elem1y;
    var elemMaxYheight = elem1height;
    for (var i = 0; i < elems.length; i++) {
        var elem2y = elemsY[i];
        var elem2height = elemsHeight[i];
        if (elem2y < elemMinY) {
            elemMinY = elem2y;
            elemMinYheight = elem2height;
        }
        if (elem2y > elemMaxY) {
            elemMaxY = elem2y;
            elemMaxYheight = elem2height;
        }
    }

    var allElemsCanBeOnSameView = (elemMaxY + elemMaxYheight - elemMinY) <= viewportHeight;

    var newViewportY;
    if (allElemsCanBeOnSameView) {
        var newViewportYmax = elemMinY;
        var newViewportYmin = elemMaxY + elemMaxYheight - viewportHeight;
        if (viewportY >= newViewportYmax) {
            newViewportY = newViewportYmax;
            newViewportY -= offset;
            if (newViewportY < newViewportYmin) {
                // constrained on both directions
                newViewportY = (newViewportYmin + newViewportYmax) / 2;
            }
        } else {
            newViewportY = newViewportYmin;
            newViewportY += offset;
            if (newViewportY > newViewportYmax) {
                newViewportY = (newViewportYmin + newViewportYmax) / 2;
            }
        }
    } else {
        var newViewportYmax = elem1y;
        var newViewportYmin = elem1y + elem1height - viewportHeight;
        // "ideal" viewport dimensions for showing all elements in one view
        var idealViewportY = elemMinY;
        var idealViewportHeight = elemMaxY + elemMaxYheight - elemMinY;
        // translate the viewport around elem1y according to location of other elements
        newViewportY = elem1y + (idealViewportY - elem1y) / idealViewportHeight * viewportHeight;
    }

    window.scrollTo({
        top: newViewportY,
        behavior: 'smooth',
    });
}

function highlightBranchClearAll() {
    var elems = document.getElementsByClassName('branch-indicator-wrapper');
    for (var i = 0; i < elems.length; i++) {
        var elem = elems[i];
        elem.classList.remove('branch-highlight-stay');
        elem.classList.remove('branch-highlight-temp');
    }
}

function highlightBranchStay(className) {
    var elems = document.getElementsByClassName(className);
    for (var i = 0; i < elems.length; i++) {
        var elem = elems[i];
        elem.parentNode.classList.add('branch-highlight-stay');
    }
}

function highlightBranchTemp(className) {
    var elems = document.getElementsByClassName(className);
    for (var i = 0; i < elems.length; i++) {
        var elem = elems[i];
        elem.parentNode.classList.add('branch-highlight-temp');
    }
}

function highlightBranchTempClear(className) {
    var elems = document.getElementsByClassName(className);
    for (var i = 0; i < elems.length; i++) {
        var elem = elems[i];
        elem.parentNode.classList.remove('branch-highlight-temp');
    }
}

function onClickBranchOrigin(elem) {
    var branchTargetElem = document.getElementById(elem.dataset.branchTarget);
    if (branchTargetElem) {
        scrollIntoView(branchTargetElem, [elem]);
    }
    highlightBranchClearAll();
    highlightBranchStay(elem.dataset.branchesClass);
}

function onClickBranchTarget(elem) {
    // get all branch origins that branch to this branch target
    var branchIndicatorsElems = document.getElementsByClassName(elem.dataset.branchesClass);
    var branchOriginsElems = [];
    for (var i = 0; i < branchIndicatorsElems.length; i++) {
        if (branchIndicatorsElems[i] != elem) {
            branchOriginsElems.push(branchIndicatorsElems[i]);
        }
    }

    // use a different origin as main scroll-to element each click
    var scrollMainElemIdx;
    if ('nextScrollMainElemIdx' in elem.dataset) {
        scrollMainElemIdx = parseInt(elem.dataset.nextScrollMainElemIdx);
    } else {
        scrollMainElemIdx = 0;
    }
    scrollMainElemIdx %= branchOriginsElems.length;
    elem.dataset.nextScrollMainElemIdx = scrollMainElemIdx + 1;

    var scrollMainElem = branchOriginsElems[scrollMainElemIdx];
    var scrollOtherElems = [elem];
    for (var i = 0; i < branchOriginsElems.length; i++) {
        if (i != scrollMainElemIdx) {
            scrollOtherElems.push(branchOriginsElems[i]);
        }
    }
    scrollIntoView(scrollMainElem, scrollOtherElems);

    highlightBranchClearAll();
    highlightBranchStay(elem.dataset.branchesClass);
}

function onMouseEnterBranchIndicator(ev) {
    highlightBranchTemp(ev.target.dataset.branchesClass,);
}

function onMouseLeaveBranchIndicator(ev) {
    highlightBranchTempClear(ev.target.dataset.branchesClass);
}

function setDiffHtml(diffHtml) {
    ASMDW.dom.diffContainer.innerHTML = diffHtml;
    var tbody = ASMDW.dom.diffContainer.getElementsByTagName('tbody')[0];
    for (var i = 0; i < tbody.children.length; i++) {
        var tr = tbody.children[i];
        for (var j = 0; j < 2 && j < tr.children.length; j++) {
            var td = tr.children[j];
            var spanChildren = td.getElementsByTagName('span');
            var wrapBranchIndicatorsElems = [];
            for (var k = 0; k < spanChildren.length; k++) {
                var spanChild = spanChildren[k];
                if ('branchesClass' in spanChild.dataset) {
                    spanChild.addEventListener('mouseenter', onMouseEnterBranchIndicator);
                    spanChild.addEventListener('mouseleave', onMouseLeaveBranchIndicator);
                    wrapBranchIndicatorsElems.push(spanChild);
                }
            }
            for (var k = 0; k < wrapBranchIndicatorsElems.length; k++) {
                var wrapBranchIndicatorElem = wrapBranchIndicatorsElems[k];
                var wrapperElem = document.createElement('span');
                wrapperElem.classList.add('branch-indicator-wrapper');
                td.insertBefore(wrapperElem, wrapBranchIndicatorElem);
                wrapBranchIndicatorElem.remove();
                wrapperElem.appendChild(wrapBranchIndicatorElem);
            }
        }
    }
}

function onNewContent() {
    var httpRequest = ASMDW.httpRequest;
    if (httpRequest.readyState == XMLHttpRequest.DONE) {
        if (httpRequest.status == 200) { // OK
            ASMDW.tryAgainAfterCommunicationFailureDelayMs = 0;
            var res = httpRequest.responseText;
            var resInfoEndIdx = res.indexOf('\n');
            var resInfo = res.slice(0, resInfoEndIdx);
            switch (resInfo) {
                case 'diff':
                    ASMDW.diffReceived++;
                    var resDiffHtml = res.slice(resInfoEndIdx + 1);
                    setDiffHtml(resDiffHtml);
                    break;
                case 'status':
                    var resStatusText = res.slice(resInfoEndIdx + 1);
                    addStatusText(resStatusText);
                    break;
                default:
                    alert('Unknown resInfo = ' + resInfo);
            }
            if (ASMDW.requestForever) {
                ASMDW.requestContentTimeoutID = setTimeout(requestContent, 100);
            }
        } else {
            if (ASMDW.tryAgainAfterCommunicationFailureDelayMs == 0) {
                ASMDW.tryAgainAfterCommunicationFailureDelayMs = 5000;
            } else {
                ASMDW.tryAgainAfterCommunicationFailureDelayMs *= 2;
            }
            var statusElem = addStatusText(
                'Failed to communicate with server, trying again in '
                + Math.round(ASMDW.tryAgainAfterCommunicationFailureDelayMs / 1000).toString()
                + ' seconds'
            );
            var retryNow = document.createElement('span');
            retryNow.appendChild(document.createTextNode('(retry now)'));
            retryNow.classList.add('communication-error-retry-now');
            retryNow.addEventListener('click', function (ev) {
                var retryNow = ev.target;
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
    var httpRequest = new XMLHttpRequest();
    ASMDW.httpRequest = httpRequest;
    httpRequest.onreadystatechange = onNewContent;
    var url = '?diff';
    if (ASMDW.diffReceived == 0)
        url += "&nowait";
    httpRequest.open('GET', url);
    httpRequest.send();
}

function onClick(ev) {
    let elem = ev.target;
    if (elem.classList.contains('branch-indicator')) {
        // branch origins have data-branch-target
        if ('branchTarget' in elem.dataset) {
            onClickBranchOrigin(elem);
        } else {
            onClickBranchTarget(elem);
        }
    } else {
        highlightBranchClearAll();
    }
}

function onBodyLoaded() {
    ASMDW.dom = {
        diffContainer: document.getElementById('diff-container'),
        statusContainer: document.getElementById('status-container'),
    };
    requestContent();
    document.body.addEventListener('click', onClick);
    requestAnimationFrame(animate);
}

// asm-differ web
window.ASMDW = {
    requestContentTimeoutID: null,
    diffReceived: 0,
    tryAgainAfterCommunicationFailureDelayMs: 0,
    statusSlideOutDurationMs: 500,
    statusElements: [],
};

var url = new URL(window.location);
ASMDW.requestForever = url.searchParams.get('once') === null;
