// src/rviz_widget.cpp
#include "rviz_widget/rviz_widget.hpp"

#include <QDebug>
#include <QShowEvent>
#include <QVBoxLayout>

#include <rclcpp/rclcpp.hpp>
#include <rviz_common/render_panel.hpp>
#include <rviz_common/visualization_manager.hpp>
#include <rviz_common/ros_integration/ros_node_abstraction.hpp>

#include <rviz_rendering/render_window.hpp>
#include <OgreViewport.h>
#include <OgreColourValue.h>

#include <rviz_common/view_manager.hpp>
#include <rviz_common/view_controller.hpp>
#include <rviz_common/tool_manager.hpp>
#include <rviz_common/tool.hpp>

RvizWidget::RvizWidget(QWidget *parent)
    : QWidget(parent)
{
    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(0);

    render_panel_ = new rviz_common::RenderPanel();
    render_panel_->setFocusPolicy(Qt::StrongFocus);
    layout->addWidget(render_panel_);

    setLayout(layout);
}

RvizWidget::~RvizWidget()
{
    delete manager_;
}

bool RvizWidget::isInitialized() const
{
    return initialized_;
}

void RvizWidget::showEvent(QShowEvent *event)
{
    QWidget::showEvent(event);

    initializeRViz();
}

void RvizWidget::setFixedFrame(const QString &frame)
{
    fixed_frame_ = frame;

    if (manager_)
        manager_->setFixedFrame(frame);
}

void RvizWidget::setRobotDescriptionTopic(const QString &topic)
{
    robot_description_topic_ = topic;

    if (robot_display_)
        robot_display_->subProp("Description Topic")->setValue(topic);
}

void RvizWidget::initializeRViz()
{
    if (initialized_)
        return;

    initialized_ = true;

    if (!rclcpp::ok()) {
        rclcpp::init(0, nullptr);
    }

    render_panel_->getRenderWindow()->initialize();

    ros_node_ = std::make_shared<rviz_common::ros_integration::RosNodeAbstraction>("rviz_widget");

    manager_ = new rviz_common::VisualizationManager(
        render_panel_,
        ros_node_,
        this,
        ros_node_->get_raw_node()->get_clock());

    render_panel_->initialize(manager_);
    manager_->initialize();
    manager_->setFixedFrame(fixed_frame_);

    auto *view_manager = manager_->getViewManager();
    view_manager->setCurrentViewControllerType("rviz_default_plugins/Orbit");

    auto *tool_manager = manager_->getToolManager();
    auto *move_camera = tool_manager->addTool("rviz_default_plugins/MoveCamera");
    tool_manager->setCurrentTool(move_camera);
    tool_manager->setDefaultTool(move_camera);
    manager_->startUpdate();

    grid_display_ = manager_->createDisplay(
        "rviz_default_plugins/Grid",
        "Grid",
        true);

    robot_display_ = manager_->createDisplay(
        "rviz_default_plugins/RobotModel",
        "RobotModel",
        true);

    const QString DESCRIPTION_SOURCE_PROP = "Description Source";
    const QString DESCRIPTION_TOPIC_PROP = "Description Topic";
    const QString DEFAULT_DESCRIPTION_SOURCE = "Topic";

    robot_display_->subProp(DESCRIPTION_SOURCE_PROP)->setValue(DEFAULT_DESCRIPTION_SOURCE);
    robot_display_->subProp(DESCRIPTION_TOPIC_PROP)->setValue(robot_description_topic_);
}

QWidget *RvizWidget::getParentWindow()
{
    return this;
}

rviz_common::PanelDockWidget *RvizWidget::addPane(
    const QString &,
    QWidget *,
    Qt::DockWidgetArea,
    bool)
{
    return nullptr;
}

void RvizWidget::setStatus(const QString &)
{
}

void RvizWidget::setOrbitView()
{
    if (manager_)
        manager_->getViewManager()->setCurrentViewControllerType("rviz_default_plugins/Orbit");
}

void RvizWidget::setFPSView()
{
    if (manager_)
        manager_->getViewManager()->setCurrentViewControllerType("rviz_default_plugins/FPS");
}

void RvizWidget::setTopDownView()
{
    if (manager_)
        manager_->getViewManager()->setCurrentViewControllerType("rviz_default_plugins/TopDownOrtho");
}

void RvizWidget::setGridVisible(bool visible)
{
    if (grid_display_)
        grid_display_->setEnabled(visible);
}

void RvizWidget::setGridColor(const QColor &color)
{
    if (grid_display_)
        grid_display_->subProp("Color")->setValue(color);
}

void RvizWidget::setGridAlpha(float alpha)
{
    if (grid_display_)
        grid_display_->subProp("Alpha")->setValue(alpha);
}

void RvizWidget::setBackgroundColor(const QColor &color)
{
    if (render_panel_) {
        auto *render_window = render_panel_->getRenderWindow();
        if (render_window) {
            auto *viewport = rviz_rendering::RenderWindowOgreAdapter::getOgreViewport(render_window);
            if (viewport) {
                viewport->setBackgroundColour(
                    Ogre::ColourValue(color.redF(), color.greenF(), color.blueF(), color.alphaF()));
            }
        }
    }
}

void RvizWidget::setRobotAlpha(float alpha)
{
    if (robot_display_)
        robot_display_->subProp("Alpha")->setValue(alpha);
}

void RvizWidget::setRobotVisible(bool visible)
{
    if (robot_display_)
        robot_display_->setEnabled(visible);
}