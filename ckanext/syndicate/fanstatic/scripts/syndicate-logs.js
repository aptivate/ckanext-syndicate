ckan.module('syndicate-log-retry', function($, _) {
    "use strict";

    function create_alert(status, text) {
      return $('<div></div>', {
        class: 'alert alert-' + status + ' alert-dismissable',
        html: '<a href="#" class="close" data-dismiss="alert" aria-label="close">&times;</a>' + text
      });
    }

    return {
        initialize: function() {
          $.proxyAll(this, /_on/);
          this.el.on('click', this._onClick);
        },
        _onClick: function(e) {
          e.preventDefault();

          var pkgId = this.options.pkgid;

          $.ajax({
            'url': '/organization/syndicate-logs/syndicate-log-retry/' + pkgId,
            'success': function(data) {
              console.dir(data)
              if (data.success) {
                $(e.target).closest('tr').remove();
                var notifications = $('.syndicate-notifications');
                var syndicateTableBody = $('#syndicate-logs-table tbody');
                var countTr = syndicateTableBody.children().length;
                var alert = create_alert('success', data.msg);

                if (!countTr) {
                  var trNothing = $('<tr></tr>', {
                    'html': '<td class="no-syndicate-logs" colspan="4"><i>There are no syndication errors.</i></td>'
                  });
                  $('#syndicate-logs-table tbody').append(trNothing);
                }
                notifications.append(alert);
              }
            }
          });
        }
    };
});

ckan.module('syndicate-log-remove', function($, _) {
    "use strict";
    return {
        initialize: function() {
          $.proxyAll(this, /_on/);
          this.el.on('click', this._onClick);
        },
        _onClick: function(e) {
          e.preventDefault();

          var pkgId = this.options.pkgid;

          $.ajax({
            'url': '/organization/syndicate-logs/syndicate-log-remove/' + pkgId,
            'success': function(data) {
              console.dir(data)
              if (data.success) {
                $(e.target).closest('tr').remove();
                var syndicateTableBody = $('#syndicate-logs-table tbody');
                var countTr = syndicateTableBody.children().length;

                if (!countTr) {
                  var trNothing = $('<tr></tr>', {
                    'html': '<td class="no-syndicate-logs" colspan="4"><i>There are no syndication errors.</i></td>'
                  });
                  $('#syndicate-logs-table tbody').append(trNothing);
                }
              }
            }
          });
        }
    };
});
