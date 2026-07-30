// src/rviz_widget.cpp
#include "rviz_widget/rviz_widget.hpp"

#include <QDebug>
#include <QResizeEvent>
#include <QShowEvent>
#include <QTimer>
#include <QVBoxLayout>
#include <QWindow>

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
    // ── Anti-flicker setup ────────────────────────────────────────────────
    // 1. Give this widget a stable native window before OGRE is initialised.
    //    Without this, Qt may destroy/recreate the OS window during resize,
    //    causing OGRE to lose its OpenGL context → flicker.
    setAttribute(Qt::WA_NativeWindow, true);

    // 2. Suppress Qt's automatic HiDPI coordinate remapping for the OGRE
    //    render surface.  At 125 % (2 K) Qt would scale up the logical-pixel
    //    coordinates and produce a resolution mismatch between the Qt layout
    //    size and the OGRE viewport size, causing continuous repaint loops.
    setAttribute(Qt::WA_DontCreateNativeAncestors, true);

    // 3. Prevent Qt from painting a background on this widget; OGRE owns the
    //    framebuffer entirely, so any Qt background paint causes a visible
    //    flash before OGRE redraws.
    setAttribute(Qt::WA_OpaquePaintEvent, true);
    setAttribute(Qt::WA_NoSystemBackground, true);
    setAutoFillBackground(false);

    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(0);

    render_panel_ = new rviz_common::RenderPanel();
    render_panel_->setFocusPolicy(Qt::StrongFocus);

    // Same attributes on the inner RenderPanel widget.
    render_panel_->setAttribute(Qt::WA_NativeWindow, true);
    render_panel_->setAttribute(Qt::WA_OpaquePaintEvent, true);
    render_panel_->setAttribute(Qt::WA_NoSystemBackground, true);
    render_panel_->setAutoFillBackground(false);

    // ── WA_PaintOnScreen: ONLY on the inner RenderPanel ─────────────────────
    // WA_PaintOnScreen tells Qt: "this widget renders directly to the screen
    // via its own OpenGL context (OGRE) — do NOT paint over it with the Qt
    // compositor".  Without this, Qt composites a background rectangle over
    // OGRE's framebuffer on every Qt repaint cycle, producing the flicker
    // visible on 2K 125% displays where Qt and OGRE repaint asynchronously.
    //
    // IMPORTANT: do NOT set WA_PaintOnScreen on the outer RvizWidget container.
    // Qt calls paintEngine() on every widget it tries to composite over; a
    // widget with WA_PaintOnScreen returns nullptr from paintEngine(), which
    // triggers the "QWidget::paintEngine: Should no longer be called" warning
    // spam.  The outer widget is a plain layout container that Qt composites
    // normally — only the OGRE-owned RenderPanel needs this flag.
    render_panel_->setAttribute(Qt::WA_PaintOnScreen, true);
    // setAttribute(Qt::WA_PaintOnScreen, true);  // ← removed: causes paintEngine spam

    layout->addWidget(render_panel_);
    setLayout(layout);

    // 4. Resize-throttle timer: coalesce rapid resize events into a single
    //    OGRE viewport update 100 ms after the last resize.  Without this,
    //    dragging the window while OGRE is updating causes frame-rate spikes
    //    and visible tearing on HiDPI displays.
    resize_timer_ = new QTimer(this);
    resize_timer_->setSingleShot(true);
    resize_timer_->setInterval(100);   // ms – tune down if resizes feel slow
    connect(resize_timer_, &QTimer::timeout, this, [this]() {
        if (render_panel_ && manager_) {
            // Force OGRE to acknowledge the new size
            render_panel_->update();
        }
    });
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
    if (!initialized_) {
        initializeRViz();
    } else if (manager_) {
        // Resume OGRE rendering when widget becomes visible again
        manager_->startUpdate();
    }
}

void RvizWidget::hideEvent(QHideEvent *event)
{
    QWidget::hideEvent(event);
    // Pause OGRE rendering while hidden to prevent:
    // - GPU buffer swaps from hidden windows conflicting with the visible one
    // - X11 compositor fighting with OGRE's framebuffer on hidden pages
    if (manager_) {
        manager_->stopUpdate();
    }
}

void RvizWidget::resizeEvent(QResizeEvent *event)
{
    QWidget::resizeEvent(event);
    // Throttle: restart the 100 ms one-shot timer on every resize.
    // OGRE viewport is only updated once the user stops resizing.
    if (resize_timer_)
        resize_timer_->start();
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
    // startUpdate() already runs at 30 Hz (33 ms) by default per RViz API.
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