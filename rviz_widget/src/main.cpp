#include <QApplication>
#include <rclcpp/rclcpp.hpp>

#include "rviz_widget/rviz_widget.hpp"

#include <iostream>

int main(int argc, char **argv)
{
    rclcpp::init(argc, argv);

    QApplication app(argc, argv);

    RvizWidget widget;
    widget.resize(900, 700);
    widget.show();
    
    int ret = app.exec();

    rclcpp::shutdown();
    return ret;
}