%Module(name=rviz_widget)

%Import QtWidgets/QtWidgetsmod.sip

class RvizWidget : QWidget
{
%TypeHeaderCode
#include "rviz_widget/rviz_widget.hpp"
%End

public:
    RvizWidget(QWidget *parent /TransferThis/ = nullptr);

    void setFixedFrame(const QString &frame);
    void setRobotDescriptionTopic(const QString &topic);
    void setOrbitView();
    void setFPSView();
    void setTopDownView();

    void setGridVisible(bool visible);
    void setGridColor(const QColor &color);
    void setGridAlpha(float alpha);

    void setBackgroundColor(const QColor &color);

    void setRobotAlpha(float alpha);
    void setRobotVisible(bool visible);
};