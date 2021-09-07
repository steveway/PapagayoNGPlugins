from krita import DockWidgetFactory, DockWidgetFactoryBase
from .krita_papagayo_import import PapagayoImporter

DOCKER_ID = 'krita_papagayo_import'
instance = Krita.instance()
dock_widget_factory = DockWidgetFactory(DOCKER_ID,
                                        DockWidgetFactoryBase.DockRight,
                                        PapagayoImporter)

instance.addDockWidgetFactory(dock_widget_factory)