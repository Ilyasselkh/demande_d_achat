# __manifest__.py

{
    'name': 'Demande d\'Achat',
    'version': '1.0',
    'summary': 'Gestion des Demandes d\'Achat',
    'sequence': 10,
    'description': """Module de gestion des demandes d'achat.""",
    'category': 'Purchases',
    'depends': ['base', 'mail', 'hr', 'account'], 
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/purchase_request_sequence.xml',
        'views/purchase_request_views.xml',
        'views/manager_centre_cout_views.xml',
        'views/purchase_request_stats_views.xml',
        'views/documentation_views.xml',
        'views/res_users_views.xml',
        'data/mail_template.xml',
        'data/purchase_request_option_data.xml',
        'report/purchase_request_report.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'demande_d_achat/static/src/css/purchase_request_form.css',
            'demande_d_achat/static/src/js/purchase_request_animations.js',
            'demande_d_achat/static/src/js/purchase_request_stats.js',
            'https://cdn.jsdelivr.net/npm/chart.js',  # CDN de Chart.js
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'icon': '/demande_d_achat/static/description/icon.png'
}
