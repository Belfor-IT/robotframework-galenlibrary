*** Settings ***
Documentation       Acceptance tests for the layout keywords (no spec files).

Library             SeleniumLibrary
Library             GalenLibrary

Suite Setup         Open Demo Page
Suite Teardown      Close All Browsers
Test Setup          Reload Page


*** Variables ***
${PAGE}         file:///${CURDIR}/resources/page.html
${BROWSER}      headlesschrome
# In Docker: add_argument("--no-sandbox");add_argument("--disable-dev-shm-usage")
${BROWSER_OPTIONS}    ${NONE}


*** Test Cases ***
Relative Positions
    Element Should Be Below    id:menu    id:header    0px
    Element Should Be Above    id:header    id:menu    0
    Element Should Be Below    id:content    id:header
    Element Should Be Left Of    css:.item    id:side-panel

Inside Container
    Element Should Be Inside    id:header    screen    0px top left right
    Element Should Be Inside    id:side-panel    viewport    0px right
    Element Should Be Inside    id:menu    viewport    partly=True

Near
    Element Should Be Near    id:header    id:menu    0px top

Sizes
    Element Height Should Be    id:header    80px
    Element Height Should Be    id:menu    35 to 45px
    Element Width Should Be    id:side-panel    200
    Element Width Should Be    id:header    100% of viewport/width

Centered
    Element Should Be Centered    id:box    id:header    vertically

Aligned Single Locator With Many Matches
    Elements Should Be Aligned    css:.item    edge=top

Aligned Several Locators
    Elements Should Be Aligned    id:header    id:menu    direction=vertically    edge=left

CSS And Colors
    Element Css Property Should Be    id:header    height    80px
    Element Css Property Should Be    id:header    background-color    rgba(34, 51, 68    match=starts
    Element Color Scheme Should Be    id:menu    > 90% #cccccc

Raw Spec
    Element Should Satisfy Spec    id:menu    below hdr 0px    height 40px    hdr=id:header

Locator Without Prefix And Xpath
    Element Should Be Below    menu    //div[@id='header']    0px

Failure Shows Galen Message
    Run Keyword And Expect Error    "menu" is 0px below "header" instead of 10px
    ...    Element Should Be Below    id:menu    id:header    10px

Failure For Size
    Run Keyword And Expect Error    "header" height is 80px instead of 50px
    ...    Element Height Should Be    id:header    50px

Unknown Element Fails Clearly
    Run Keyword And Expect Error    "does-not-exist" is absent on page
    ...    Element Height Should Be    id:does-not-exist    50px


*** Keywords ***
Open Demo Page
    Open Browser    ${PAGE}    ${BROWSER}    options=${BROWSER_OPTIONS}
    Set Window Size    1280    900
