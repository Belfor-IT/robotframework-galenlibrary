*** Settings ***
Documentation       Acceptance tests for GalenLibrary against a local page in headless Chrome.
...                 Run from the package folder: robot --outputdir results atest

Library             SeleniumLibrary
Library             GalenLibrary
Library             OperatingSystem

Suite Setup         Open Demo Page
Suite Teardown      Close All Browsers


*** Variables ***
${PAGE}         file:///${CURDIR}/resources/page.html
${SPEC}         ${CURDIR}/resources/page.gspec
${BROWSER}      headlesschrome
# In Docker: add_argument("--no-sandbox");add_argument("--disable-dev-shm-usage")
${BROWSER_OPTIONS}    ${NONE}


*** Test Cases ***
Layout Is Valid On Desktop
    Set Window Size    1280    900
    Check Layout    ${SPEC}    desktop

Layout Is Valid On Mobile
    Set Window Size    500    900
    Check Layout    ${SPEC}    mobile
    [Teardown]    Set Window Size    1280    900

Broken Layout Fails With Galen Message
    Run Keyword And Expect Error    *failed with 1 error(s)*"menu" height is 40px instead of 100px*
    ...    Check Layout    ${SPEC}    desktop, broken

Result Can Be Inspected Without Failing
    ${result} =    Check Layout    ${SPEC}    tags=broken    fail_on_error=False
    Should Be Equal As Integers    ${result}[errors]    1
    File Should Exist    ${result}[report_path]

Uses Same Browser Session As SeleniumLibrary
    [Documentation]    A change made through SeleniumLibrary is seen by Galen.
    Execute Javascript    document.getElementById('menu').style.height = '100px'
    Run Keyword And Expect Error    *"menu" height is 100px instead of 40px*
    ...    Check Layout    ${SPEC}    desktop
    [Teardown]    Reload Page


*** Keywords ***
Open Demo Page
    Open Browser    ${PAGE}    ${BROWSER}    options=${BROWSER_OPTIONS}
    Set Window Size    1280    900
