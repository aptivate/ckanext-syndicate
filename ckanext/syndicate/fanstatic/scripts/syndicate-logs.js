ckan.module('syndicate-log-retry', function($, _) {
    "use strict";

    return {
        initialize: function() {
          $.proxyAll(this, /_on/);
          this.el.on('click', this._onClick);
        },
        _onClick: function(e) {
          e.preventDefault();

          var pkgId = this.options.pkgid;
          var self = this;

          $.ajax({
            'url': this.options.site_url + '/organization/syndicate-logs/syndicate-log-retry/' + pkgId,
            'success': function(data) {

              if (data.success) {
                $(e.target).closest('tr').remove();
                var syndicateTableBody = $('#syndicate-logs-table tbody');
                var countTr = syndicateTableBody.children().length;

                self.sandbox.notify('Success', data.msg, 'success');

                if (!countTr) {
                  var trNothing = $('<tr></tr>', {
                    'html': '<td class="no-syndicate-logs" colspan="5"><i>There are no syndication errors.</i></td>'
                  });
                  $('#syndicate-logs-table tbody').append(trNothing);
                }
              } else {
                self.sandbox.notify('Success', data.msg, 'error');
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
            'url': this.options.site_url + '/organization/syndicate-logs/syndicate-log-remove/' + pkgId,
            'success': function(data) {

              if (data.success) {
                $(e.target).closest('tr').remove();
                var syndicateTableBody = $('#syndicate-logs-table tbody');
                var countTr = syndicateTableBody.children().length;

                if (!countTr) {
                  var trNothing = $('<tr></tr>', {
                    'html': '<td class="no-syndicate-logs" colspan="5"><i>There are no syndication errors.</i></td>'
                  });
                  $('#syndicate-logs-table tbody').append(trNothing);
                }
              }
            }
          });
        }
    };
});
