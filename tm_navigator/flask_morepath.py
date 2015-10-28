from collections import namedtuple
import re
from itertools import chain
from functools import cmp_to_key
from cached_property import cached_property
import flask
from flask.ext.mako import render_template, render_template_def
from markupsafe import Markup


class Endpoint(namedtuple('Endpoint', ['name', 'rule'])):
    @cached_property
    def rule_keys(self):
        return re.findall(r'<(?:\w+:)?(\w+)>', self.rule)

    def get_dict(self, ui, values):
        custom_params = getattr(ui, 'to_url', lambda: {})()
        dct = {key: getattr(ui.model, key)
               for key in self.rule_keys
               if key not in values and key not in custom_params}
        dct.update(custom_params)
        dct.update(values)
        return dct


class Template(namedtuple('Template', ['file', 'views'])):
    class NotFound(Exception):
        pass

    def render(self, view_name, **kwargs):
        if view_name == '':
            return render_template(self.file, **kwargs)
        elif self.views is not None and view_name not in self.views:
            raise self.NotFound('View "%s" in file "%s"' % (view_name, self.file))
        else:
            def_name = 'view_%s' % view_name
            return render_template_def(self.file, def_name, **kwargs)


class SubclassDict:
    def __init__(self):
        self.dct = {}

    def __setitem__(self, key, value):
        self.dct[key] = value

    def __getitem__(self, key):
        if key not in self.dct:
            keys = [
                k
                for k in self.dct.keys()
                if issubclass(key, k)
            ]
            if not keys:
                self.dct[key] = KeyError
            else:
                newkey = min(keys,
                             key=cmp_to_key(lambda x, y:
                                            -1 if issubclass(x, y)
                                            else 1 if issubclass(y, x)
                                            else 0))
                self.dct[key] = self.dct[newkey]

        if self.dct[key] == KeyError:
            raise KeyError
        return self.dct[key]

    def __contains__(self, key):
        try:
            self.__getitem__(key)
            return True
        except KeyError:
            return False

    def get(self, key, default):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default


class Morepath:
    def __init__(self, app=None):
        self._app = app
        app.context_processor(lambda: {'mp': self})

        self.ui_for_model = SubclassDict()
        self.model_for_ui = dict()
        self.templates = dict()
        self.endpoints = dict()

    @property
    def app(self):
        return self._app or flask.current_app

    def ui_for(self, model_cls):
        def add_alias(original_ui_cls):
            if getattr(original_ui_cls, '_uiclass', False):
                ui_class = original_ui_cls
            else:
                class ui_class(original_ui_cls):
                    def __init__(self, model):
                        self.model = model

                ui_class.__name__ = original_ui_cls.__name__
                ui_class._uiclass = True

            self.ui_for_model[model_cls] = ui_class

            if ui_class in self.model_for_ui:
                self.model_for_ui[ui_class] = None  # don't support multiple models for ui here
            else:
                self.model_for_ui[ui_class] = model_cls
            return ui_class

        return add_alias

    def _get_ui(self, model_or_ui):
        model_cls = model_or_ui.__class__
        if model_cls in self.ui_for_model:
            ui_cls = self.ui_for_model.get(model_cls, model_cls)
            return ui_cls(model_or_ui)
        else:
            return model_or_ui

    def template(self, template, views=()):
        def add_template(ui_cls):
            self.templates[ui_cls] = Template(template, views)
            return ui_cls

        return add_template

    def route(self, rule, **route_options):
        assert rule.endswith('/')

        def add_route(ui_cls):
            if 'endpoint' not in route_options:
                route_options['endpoint'] = '_%s' % self.model_for_ui.get(ui_cls, ui_cls).__name__
            self.endpoints[ui_cls] = Endpoint(name=route_options['endpoint'], rule=rule)

            if not hasattr(ui_cls, '_flask_route_handler'):
                def wrapped(*args, _view_name='', **kwargs):
                    ui_or_model = getattr(ui_cls, 'from_url', ui_cls)(*args, **kwargs)
                    if ui_or_model is None:
                        flask.abort(404)

                    if callable(ui_or_model):
                        ui_or_model = ui_or_model()

                    try:
                        return self.get_view(ui_or_model, _view_name)
                    except Template.NotFound:
                        flask.abort(404)

                ui_cls._flask_route_handler = wrapped

            self.app.route(rule, **route_options)(ui_cls._flask_route_handler)
            self.app.route('%s<_view_name>' % rule, **route_options)(ui_cls._flask_route_handler)

            return ui_cls

        return add_route

    def get_view(self, ui_or_model, view='', **kwargs):
        with self.app.extensions['sqlalchemy'].db.session.no_autoflush:  # XXX
            ui = self._get_ui(ui_or_model)

            if ui.__class__ in self.templates:
                result = self.templates[ui.__class__].render(view, s=ui, **kwargs)
                return Markup(result)
            else:
                return ui

    def url_for(self, ui_or_model=None, *, view='', **values):
        if ui_or_model is None:
            return flask.url_for('static', **values)

        if isinstance(ui_or_model, type):
            ui_or_model = ui_or_model()

        ui = self._get_ui(ui_or_model)
        endpoint = self.endpoints[ui.__class__]
        values = endpoint.get_dict(ui, values)

        return flask.url_for(endpoint.name, _view_name=view, **values)

    def errorhandler(self, code_or_exception=None):
        def add_handler(ui_cls):
            def wrapped(error):
                model = ui_cls(error)
                return self.get_view(model), getattr(error, 'code', 500)

            if code_or_exception is None:
                for code in chain(range(400, 420), range(500, 506)):
                    self.app.errorhandler(code)(wrapped)
                self.app.errorhandler(Exception)(wrapped)
            else:
                self.app.errorhandler(code_or_exception)(wrapped)

            return ui_cls

        return add_handler


def url_for_cached(endpoint, **values):
    key = (endpoint,
           tuple((k, v) for k, v in values.items() if k[0] == '_'),
           tuple(k for k in values.keys() if k[0] != '_'))

    if key not in url_for_cached.cache:
        url_for_cached.cache[key] = flask_url_for(endpoint,
                                                  **{k: (v if k[0] == '_' else hash(k))
                                                     for k, v in values.items()})
        for k, v in values.items():
            if k[0] != '_':
                url_for_cached.cache[key] = url_for_cached.cache[key].replace(str(hash(k)), '{%s}' % k)

    result = url_for_cached.cache[key].format(**{k: v for k, v in values.items() if k[0] != '_'})
    return result

url_for_cached.cache = {}
flask_url_for = flask.url_for
flask.url_for = url_for_cached
