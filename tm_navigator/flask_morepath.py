from collections import namedtuple, defaultdict
import re
from itertools import chain
from functools import cmp_to_key
from cached_property import cached_property
import flask
from flask.ext.mako import render_template, render_template_def


class Endpoint(namedtuple('Endpoint', ['name', 'rule', 'to_url', 'from_url'])):
    @cached_property
    def rule_keys(self):
        return re.findall(r'<(?:\w+:)?(\w+)>', self.rule)

    def get_dict(self, model, values):
        custom_params = self.to_url(model)
        dct = {key: getattr(model, key)
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
        elif view_name not in self.views:
            raise self.NotFound
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

    def __contains__(self, item):
        try:
            self.__getitem__(item)
            return True
        except KeyError:
            return False


class Morepath:
    def __init__(self, app=None):
        self._app = app
        app.context_processor(lambda: {'mp': self})

        self.aliases = SubclassDict()
        self.aliases_reversed = defaultdict(list)
        self.templates = SubclassDict()
        self.endpoints = SubclassDict()

    @property
    def app(self):
        return self._app or flask.current_app

    def ui_for(self, a):
        def add_alias(original_cls):
            self.aliases[a] = original_cls
            self.aliases_reversed[original_cls].append(a)
            return original_cls

        return add_alias

    def _unalias(self, cls):
        try:
            return self.aliases[cls]
        except KeyError:
            return cls

    def template(self, template, views=()):
        def add_template(cls):
            self.templates[cls] = Template(template, views)
            return cls

        return add_template

    def route(self, rule, to_url=lambda m: {}, from_url=lambda m: {}, **route_options):
        assert rule.endswith('/')

        def add_route(cls):
            if 'endpoint' not in route_options:
                route_options['endpoint'] = '_%s' % self.aliases_reversed.get(cls, [cls])[0].__name__
            self.endpoints[cls] = Endpoint(name=route_options['endpoint'], rule=rule, to_url=to_url, from_url=from_url)

            if not hasattr(cls, '_flask_route_handler'):
                def wrapped(*args, _view_name='', **kwargs):
                    model = cls(*args, **kwargs)
                    try:
                        return self.get_view(model, _view_name)
                    except Template.NotFound:
                        flask.abort(404)

                cls._flask_route_handler = wrapped

            self.app.route(rule, **route_options)(cls._flask_route_handler)
            self.app.route('%s<_view_name>' % rule, **route_options)(cls._flask_route_handler)

            return cls

        return add_route

    def get_view(self, model, view=''):
        cls = self._unalias(model.__class__)

        with self.app.extensions['sqlalchemy'].db.session.no_autoflush:
            result = model() if callable(model) else model

            if cls in self.templates:
                return self.templates[cls].render(view, s=result)
            else:
                return result

    def url_for(self, model=None, *, view='', **values):
        if model is None:
            return flask.url_for('static', **values)

        if isinstance(model, type):
            model = model()

        cls = self._unalias(model.__class__)
        endpoint = self.endpoints[cls]
        values = endpoint.get_dict(model, values)

        return flask.url_for(endpoint.name, _view_name=view, **values)

    def errorhandler(self, code_or_exception=None):
        def add_handler(cls):
            def wrapped(error):
                model = cls(error)
                return self.get_view(model), getattr(error, 'code', 500)

            if code_or_exception is None:
                for code in chain(range(400, 420), range(500, 506)):
                    self.app.errorhandler(code)(wrapped)
                self.app.errorhandler(Exception)(wrapped)
            else:
                self.app.errorhandler(code_or_exception)(wrapped)

            return cls

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
