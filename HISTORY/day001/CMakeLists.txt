cmake_minimum_required(VERSION 3.28)

project(AiriDL VERSION 0.1.0 LANGUAGES CXX)
set(CMAKE_CXX_EXTENSIONS OFF)

include(CTest)

option(AIRIDL_ENABLE_SANITIZERS "Enable AddressSanitizer and UBSan" OFF)

add_library(airidl_core STATIC cpp/runtime/version.cpp)
add_library(airidl::core ALIAS airidl_core)
target_compile_features(airidl_core PUBLIC cxx_std_20)
target_include_directories(
    airidl_core
    PUBLIC "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/cpp/include>"
)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(airidl_core PRIVATE -Wall -Wextra -Wpedantic)
    if(AIRIDL_ENABLE_SANITIZERS)
        target_compile_options(airidl_core PUBLIC -fsanitize=address,undefined -fno-omit-frame-pointer)
        target_link_options(airidl_core PUBLIC -fsanitize=address,undefined)
    endif()
elseif(MSVC)
    target_compile_options(airidl_core PRIVATE /W4)
endif()

if(BUILD_TESTING)
    add_executable(airidl_core_test cpp/tests/version_test.cpp)
    target_link_libraries(airidl_core_test PRIVATE airidl::core)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(airidl_core_test PRIVATE -Wall -Wextra -Wpedantic)
    elseif(MSVC)
        target_compile_options(airidl_core_test PRIVATE /W4)
    endif()
    add_test(NAME cpp.core_version COMMAND airidl_core_test)
endif()
