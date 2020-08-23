""" Tools to help plucking SqlAlchemy instances

Plucking is normally done by SALoadedModel.from_orm(), but it needs some help.
Without our assistance, it would get every loaded attribute it can.
This may include @property attributes that will in turn trigger the loading of other nested attributes.

To help with this, "selection dictionaries" are used, which look like this:

    {'id': 1, 'name': 1, 'property': 1}

Those dictionaries explicitly specify which attributes to load.
"""
# TODO
