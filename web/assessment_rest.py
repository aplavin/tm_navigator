from flask import session, request
from app import restless
from assessment_models import *


class classproperty(object):
    def __init__(self, fget):
        self.fget = fget

    def __get__(self, owner_self, owner_cls):
        return self.fget(owner_cls)


def fill_fields_auto(data, **kw):
    if 'username' in session:
        data['username'] = session['username']
    data['technical_info'] = {
        'user_agent': request.user_agent.string,
        'referrer': request.referrer,
        'access_route': request.access_route
    }


for model in (m for m in Base._decl_class_registry.values()
              if getattr(m, '__name__', '').startswith('A')):
    restless.create_api(model,
                        methods=['GET', 'POST'],
                        preprocessors={'POST': [fill_fields_auto]})
    model.url = classproperty(lambda cls, model=model: restless.url_for(model))
