#include <QApplication>
#include <QWebView>
#include <QUrl>


int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    QWebView view;
    view.load(QUrl(argv[1]));
    view.show();
    return app.exec();
}
