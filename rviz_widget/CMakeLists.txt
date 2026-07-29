cmake_minimum_required(VERSION 3.8)
project(rviz_widget)

set(CMAKE_AUTOMOC ON)

find_package(ament_cmake REQUIRED)
find_package(Qt5 REQUIRED COMPONENTS Widgets)
find_package(rclcpp REQUIRED)
find_package(rviz_common REQUIRED)
find_package(rviz_rendering REQUIRED)
find_package(rviz_default_plugins REQUIRED)

add_library(rviz_widget SHARED
    src/rviz_widget.cpp
)

target_include_directories(rviz_widget PRIVATE
    include
)

target_link_libraries(rviz_widget
    Qt5::Widgets
)

ament_target_dependencies(rviz_widget
    rclcpp
    rviz_common
    rviz_rendering
    rviz_default_plugins
)

add_executable(rviz_widget_demo
    src/main.cpp
)

target_include_directories(rviz_widget_demo PRIVATE
    include
)

target_link_libraries(rviz_widget_demo
    rviz_widget
)

ament_target_dependencies(rviz_widget_demo
    rclcpp
    rviz_common
    rviz_rendering
    rviz_default_plugins
)

install(
    TARGETS rviz_widget rviz_widget_demo
    ARCHIVE DESTINATION lib
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION lib/${PROJECT_NAME}
)

find_program(SIP_BUILD_EXECUTABLE sip-build REQUIRED)

add_custom_target(
    rviz_widget_python ALL
    COMMAND ${SIP_BUILD_EXECUTABLE}
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    COMMENT "Building SIP Python bindings"
)

add_dependencies(rviz_widget_python rviz_widget)

ament_package()