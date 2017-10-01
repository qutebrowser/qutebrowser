#include <QApplication>
#include <QWebEngineView>
#include <QUrl>


int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    QWebEngineView view;
    view.load(QUrl(argv[1]));
    view.show();
    return app.exec();
}
