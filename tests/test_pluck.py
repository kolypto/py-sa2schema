import pytest
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base

import sa2schema as sa2
from .lib import sa_set_committed_state


def test_pluck():
    """ Test sa_pluck() """
    Base = declarative_base()

    class User(Base):
        __tablename__ = 'users'
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String)
        meta = sa.Column(sa.JSON)
        articles = sa.orm.relationship(lambda: Article, back_populates='author')

        unloaded = sa.Column(sa.String)

        @property
        def prop(self):
            return 'hey'

        assprox = sa.ext.associationproxy.association_proxy(
            'articles',
            'title'
        )

    class Article(Base):
        __tablename__ = 'articles'
        id = sa.Column(sa.Integer, primary_key=True)
        title = sa.Column(sa.String)
        author_id = sa.Column(sa.ForeignKey(User.id))
        author = sa.orm.relationship(User, back_populates='articles')

    u = sa_set_committed_state(User(), id=17, name='John', meta={'a': 1, 'b': {'c': 2, 'd': 3}}, articles=[
        sa_set_committed_state(Article(), id=100, author_id=17, title='Python'),
        sa_set_committed_state(Article(), id=101, author_id=17, title='Rust'),
        sa_set_committed_state(Article(), id=102, author_id=17, title='C++'),
    ])

    # Just make sure that the recursive link is there
    for article in u.articles:
        sa_set_committed_state(article, author=u)

    # Test: Pluck: attribute:1, attribute:0
    assert sa2.sa_pluck(u, {}) == {}
    assert sa2.sa_pluck(u, {'id': 0}) == {}
    assert sa2.sa_pluck(u, {'id': 1}) == {'id': 17}
    assert sa2.sa_pluck(u, {'id': 1, 'name': 1}) == {'id': 17, 'name': 'John'}

    # Test: invalid attribute name
    # NOTE: no error is raised; default value is returned
    with pytest.raises(AttributeError):
        assert sa2.sa_pluck(u, {'INVALID': 1}) == {'INVALID': None}

    with pytest.raises(AttributeError):
        assert sa2.sa_pluck(u, {'INVALID': 1}, sa2.Unloaded.LAZY) == {'INVALID': None}

    assert sa2.sa_pluck(u, {'INVALID': 1}, sa2.Unloaded.NONE) == {'INVALID': None}


    # Test: Pluck: JSON attribute. Nested plucks
    assert sa2.sa_pluck(u, {'meta': 1}) == {'meta': {'a': 1, 'b': {'c': 2, 'd': 3}}}  # the whole attr
    assert sa2.sa_pluck(u, {'meta': {'a': 1}}) == {'meta': {'a': 1}}  # sub-key
    assert sa2.sa_pluck(u, {'meta': {'b': 1}}) == {'meta': {'b': {'c': 2, 'd': 3}}}  # sub-key which is a dict
    assert sa2.sa_pluck(u, {'meta': {'b': {'c': 2}}}) == {'meta': {'b': {'c': 2}}}  # sub-sub-key
    assert sa2.sa_pluck(u, {'meta': {'INVALID': 1}}) == {'meta': {}}  # invalid key forgiven
    assert sa2.sa_pluck(u, {'meta': {'a': {'NONDICT': 1}}}) == {'meta': {'a': 1}}  # invalid structure forgiven

    # Test: relationship array
    assert sa2.sa_pluck(u, {'articles': {}}) == {'articles': []}  # nothing to pluck, nothing to return
    assert sa2.sa_pluck(u, {'articles': {'id': 1}}) == {'articles': [{'id': 100}, {'id': 101}, {'id': 102}]}

    with pytest.raises(AttributeError):
        sa2.sa_pluck(u, {'articles': 1})  # can't map relationships to `1`

    # Test: relationship scalar
    a = u.articles[0]
    assert sa2.sa_pluck(a, {'title': 1}) == {'title': 'Python'}
    assert sa2.sa_pluck(a, {'author': {'id': 1}}) == {'author': {'id': 17}}
    assert sa2.sa_pluck(a, {'author': {}}) == {'author': {}}

    # Test: relationship has no loaded value
    u = sa_set_committed_state(User(), id=17, articles=None)
    assert sa2.sa_pluck(u, {'articles': {'id': 1}}) == {'articles': []}  # skipped

    # Test: @property
    assert sa2.sa_pluck(u, {'prop': 1}, sa2.Unloaded.NONE) == {'prop': 'hey'}  # value is here, even though not in __dict__
    assert sa2.sa_pluck(u, {'prop': 1}, sa2.Unloaded.LAZY) == {'prop': 'hey'}  # getattr() works
    assert sa2.sa_pluck(u, {'prop': 1}, sa2.Unloaded.RAISE) == {'prop': 'hey'}  # works

    # Test: association proxy (because it's a descriptor)
    assert sa2.sa_pluck(u, {'assprox': 1}) == {'assprox': []}
