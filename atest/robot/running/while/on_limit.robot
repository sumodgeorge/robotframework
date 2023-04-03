*** Settings ***
Suite Setup       Run Tests    ${EMPTY}    running/while/on_limit.robot
Resource          while.resource

*** Test Cases ***
On limit pass without limit defined
    Check Test Case    ${TESTNAME}

On limit pass with time limit defined
    Check Test Case    ${TESTNAME}

On limit pass with iteration limit defined
    Check Test Case    ${TESTNAME}

On limit message without limit
    Check Test Case    ${TESTNAME}

On limit fail
    Check Test Case    ${TESTNAME}

On limit pass with failures in loop
    Check Test Case    ${TESTNAME}

Invalid on_limit
    Check Test Case    ${TESTNAME}

Wrong WHILE argument
    Check Test Case    ${TESTNAME}

On limit message
    Check Test Case    ${TESTNAME}

On limit message from variable
    Check Test Case    ${TESTNAME}

Part of on limit message from variable
    Check Test Case    ${TESTNAME}

No on limit message
    Check Test Case    ${TESTNAME}

Nested while on limit message
    Check Test Case    ${TESTNAME}

On limit message before limit
    Check Test Case    ${TESTNAME}

Wrong WHILE arguments
    Check Test Case    ${TESTNAME}
