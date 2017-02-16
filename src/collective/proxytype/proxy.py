# -*- coding: utf-8 -*-
from .interfaces import IProxyType
from bs4 import UnicodeDammit
from lxml.html.clean import clean_html

import lxml
import plone.api.portal
import re
import requests


def get_content(
    remote_url,
    content_selector=None,
    append_script=False,
    append_style=False,
    append_link=False
):
    """Get remote html content.
    """

    res = requests.get(remote_url)

    content_type = res.headers['Content-Type']
    if 'text/html' not in content_type:
        # CASE NON-HTML CONTENT (IMAGES/JAVASCRIPT/CSS/WHATEVER)
        return (res.content, content_type)

    # CASE HTML

    # Cleanup...?
    # response = UnicodeDammit(res.text).unicode_markup
    # text = clean_html(res.text)

    # Replace all relative URLs to absolute ones.
    tree = lxml.html.fromstring(res.text)
    tree.make_links_absolute(remote_url)

    c_tree = tree.cssselect(content_selector) if content_selector else [tree]

    append = []
    if append_script:
        append += tree.cssselect('html head script')
    if append_style:
        append += tree.cssselect('html head style')
    if append_link:
        append += tree.cssselect('html head link')

    for el in append:
        # Append to last selected element
        c_tree[-1].append(el)

    # serialize all selected elements in order from the content tree
    ret = u'\n'.join([
        lxml.html.tostring(el, encoding='unicode')
        for el in c_tree
    ])

    cat = plone.api.portal.get_tool('portal_catalog')
    res = cat.searchResults(
        object_provides=IProxyType.__identifier__
    )

    # Create a list of remote_url, absolute_url tuples for the replacement
    repl_map = [
        (
            it.getObject().remote_url,
            u'{0}/@@proxyview/'.format(it.getObject().absolute_url()),
            it.getObject().exclude_urls
        )
        for it in res
    ]

    # Reverse sort the replacement values to support proxyviews in proxyviews
    repl_map.sort(
        key=lambda el: el[1],
        reverse=True
    )

    # Now, for all IProxyType, replace their remote_url with their absolute_url
    for remote_url_, absolute_url_, exclude_urls_ in repl_map:
        if exclude_urls_:
            rec = re.compile('(?!({0})){1}'.format(
                '|'.join(exclude_urls_),
                remote_url_
            ))
        else:
            rec = re.compile(remote_url_)
        ret = rec.sub(absolute_url_, ret)

        # Replace double-googles within the @@proxyview path.
        # Traversing to those doesn't work.
        rec = re.compile('(?!(\/@@proxyview))\/@@')
        ret = rec.sub('', ret)

    return (ret, content_type)
