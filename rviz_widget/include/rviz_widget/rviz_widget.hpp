// include/rviz_widget/rviz_widget.hpp
#pragma once

#include <QWidget>
#include <QColor>
#include <QHideEvent>
#include <QResizeEvent>
#include <QTimer>
#include <memory>

#include <rviz_common/window_manager_interface.hpp>
#include <rviz_common/display.hpp>

namespace rviz_common
{
class RenderPanel;
class VisualizationManager;
namespace ros_integration
{
class RosNodeAbstraction;
}
class PanelDockWidget;
}

class RvizWidget : public QWidget, public rviz_common::WindowManagerInterface
{
public:
    explicit RvizWidget(QWidget *parent = nullptr);
    ~RvizWidget() override;

    void setFixedFrame(const QString &frame);
    void setRobotDescriptionTopic(const QString &topic);
    void setOrbitView();
    void setFPSView();
    void setTopDownView();
    bool isInitialized() const;

    void setGridVisible(bool visible);
    void setGridColor(const QColor &color);
    void setGridAlpha(float alpha);

    void setBackgroundColor(const QColor &color);

    void setRobotAlpha(float alpha);
    void setRobotVisible(bool visible);

protected:
    void showEvent(QShowEvent *event) override;
    void hideEvent(QHideEvent *event) override;
    void resizeEvent(QResizeEvent *event) override;

public:
    QWidget *getParentWindow() override;
    rviz_common::PanelDockWidget *addPane(
        const QString &name,
        QWidget *pane,
        Qt::DockWidgetArea area = Qt::LeftDockWidgetArea,
        bool floating = false) override;
    void setStatus(const QString &message) override;

private:
    QString fixed_frame_{"base_link"};
    QString robot_description_topic_{"/robot_description"};
    bool initialized_{false};
    std::shared_ptr<rviz_common::ros_integration::RosNodeAbstraction> ros_node_;
    rviz_common::RenderPanel *render_panel_{nullptr};
    rviz_common::VisualizationManager *manager_{nullptr};
    rviz_common::Display *grid_display_{nullptr};
    rviz_common::Display *robot_display_{nullptr};
    QTimer *resize_timer_{nullptr};
    void initializeRViz();
};