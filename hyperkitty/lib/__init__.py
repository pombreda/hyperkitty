#-*- coding: utf-8 -*-
# Copyright (C) 1998-2012 by the Free Software Foundation, Inc.
#
# This file is part of HyperKitty.
#
# HyperKitty is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# HyperKitty is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# HyperKitty.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Aurelien Bompard <abompard@fedoraproject.org>
#

import urllib
from hashlib import md5
import datetime

from django.core.exceptions import SuspiciousOperation
from django.core.mail import EmailMessage
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from mailmanclient import MailmanConnectionError

from hyperkitty.lib import mailman


FLASH_MESSAGES = {
    "updated-ok": ("success", "The profile was successfully updated."),
    "sent-ok": ("success", "The message has been sent successfully."),
}


def gravatar_url(email):
    '''Return a gravatar url for an email address'''
    size = 64
    default = "http://fedoraproject.org/static/images/" + \
            "fedora_infinity_%ix%i.png" % (size, size)
    query_string = urllib.urlencode({'s': size, 'd': default})
    identifier = md5(email).hexdigest()
    return 'http://www.gravatar.com/avatar/%s?%s' % (identifier, query_string)


def get_months(store, list_name):
    """ Return a dictionnary of years, months for which there are
    potentially archives available for a given list (based on the
    oldest post on the list).

    :arg list_name, name of the mailing list in which this email
    should be searched.
    """
    date_first = store.get_start_date(list_name)
    if not date_first:
        return {}
    archives = {}
    now = datetime.datetime.now()
    year = date_first.year
    month = date_first.month
    while year < now.year:
        archives[year] = range(1, 13)[(month -1):]
        year = year + 1
        month = 1
    archives[now.year] = range(1, 13)[:now.month]
    return archives


def get_store(request):
    return request.environ["kittystore.store"]


def stripped_subject(mlist, subject):
    if mlist is None:
        return subject
    if subject.lower().startswith(mlist.subject_prefix.lower()):
        subject = subject[len(mlist.subject_prefix) : ]
    return subject


def get_display_dates(year, month, day):
    if day is None:
        start_day = 1
    else:
        start_day = int(day)
    begin_date = datetime.datetime(int(year), int(month), start_day)

    if day is None:
        end_date = begin_date + datetime.timedelta(days=32)
        end_date = end_date.replace(day=1)
    else:
        end_date = begin_date + datetime.timedelta(days=1)

    return begin_date, end_date


def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + datetime.timedelta(n)


class PostingFailed(Exception): pass

def post_to_list(request, mlist, subject, message, headers={}):
    if not mlist:
        # Make sure the list exists to avoid posting to any email addess
        raise SuspiciousOperation("I don't know this mailing-list")
    # Check that the user is subscribed
    try:
        mailman.subscribe(mlist.name, request.user)
    except MailmanConnectionError:
        raise PostingFailed("Can't connect to Mailman's REST server, "
                            "your message has not been sent.")
    # send the message
    headers["User-Agent"] = "HyperKitty on %s" % request.build_absolute_uri("/")
    msg = EmailMessage(
               subject=subject,
               body=message,
               from_email='"%s %s" <%s>' %
                   (request.user.first_name, request.user.last_name,
                    request.user.email),
               to=[mlist.name],
               headers=headers,
               )
    msg.send()


def paginate(objects, page_num, max_page_range=10, paginator=None):
    try:
        page_num = int(page_num)
    except (TypeError, ValueError):
        page_num = 1
    if paginator is None:
        paginator = Paginator(objects, 10) # else use the provided instance
    try:
        objects = paginator.page(page_num)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        objects = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        objects = paginator.page(paginator.num_pages)
    # Calculate the displayed page range
    if paginator.num_pages > max_page_range:
        objects.page_range = [ 1 ]
        subrange_lower = page_num - (max_page_range / 2 - 2)
        if subrange_lower > 3:
            objects.page_range.append("...")
        else:
            subrange_lower = 2
        objects.page_range.extend(range(subrange_lower, page_num))
        if page_num != 1 and page_num != 100:
            objects.page_range.append(page_num)
        subrange_upper = page_num + (max_page_range / 2 - 2)
        if subrange_upper >= paginator.num_pages - 2:
            subrange_upper = paginator.num_pages - 1
        objects.page_range.extend(range(page_num+1, subrange_upper+1))
        if subrange_upper < paginator.num_pages - 2:
            objects.page_range.append("...")
        objects.page_range.append(paginator.num_pages)
    else:
        objects.page_range = [ p+1 for p in range(paginator.num_pages) ]
    return objects

