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
function scrollIntoView(elem1, elems) {
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
        elem.classList.remove('branch-highlight-stay');
        elem.classList.remove('branch-highlight-temp');
    }
}

function highlightBranchStay(className) {
    for (let elem of document.getElementsByClassName(className)) {
        elem.parentNode.classList.add('branch-highlight-stay');
    }
}

function highlightBranchTemp(className) {
    for (let elem of document.getElementsByClassName(className)) {
        elem.parentNode.classList.add('branch-highlight-temp');
    }
}

function highlightBranchTempClear(className) {
    for (let elem of document.getElementsByClassName(className)) {
        elem.parentNode.classList.remove('branch-highlight-temp');
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

function onClickBranchTarget(elem) {
    // get all branch origins that branch to this branch target
    let branchOriginsElems = [];
    for (let branchIndicatorElem of document.getElementsByClassName(elem.dataset.branchesClass)) {
        if (branchIndicatorElem != elem) {
            branchOriginsElems.push(branchIndicatorElem);
        }
    }

    // use a different origin as main scroll-to element each click
    let scrollMainElemIdx;
    if ('nextScrollMainElemIdx' in elem.dataset) {
        scrollMainElemIdx = parseInt(elem.dataset.nextScrollMainElemIdx);
    } else {
        scrollMainElemIdx = 0;
    }
    scrollMainElemIdx %= branchOriginsElems.length;
    elem.dataset.nextScrollMainElemIdx = scrollMainElemIdx + 1;

    let scrollMainElem = branchOriginsElems[scrollMainElemIdx];
    let scrollOtherElems = [elem];
    for (let i = 0; i < branchOriginsElems.length; i++) {
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
    let tbody = ASMDW.dom.diffContainer.getElementsByTagName('tbody')[0];
    for (let tr of tbody.children) {
        for (let j = 0; j < 2 && j < tr.children.length; j++) {
            let td = tr.children[j];
            for (let spanChild of td.getElementsByTagName('span')) {
                if ('branchesClass' in spanChild.dataset) {
                    spanChild.addEventListener('mouseenter', onMouseEnterBranchIndicator);
                    spanChild.addEventListener('mouseleave', onMouseLeaveBranchIndicator);
                }
            }
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
            switch (resInfo) {
                case 'diff':
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

let url = new URL(window.location);
ASMDW.requestForever = url.searchParams.get('once') === null;
