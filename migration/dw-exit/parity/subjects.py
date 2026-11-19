"""Subject-area execution contracts for local relational parity."""

SUBJECTS = {
    'billing': {
        'stages': ('10_load.sql', '15_storage.sql', '20_routines.sql', '30_views.sql', '40_close.sql'),
        'procedure': 'P_MONTHLY_INVOICE',
    },
    'users': {
        'stages': ('10_load.sql', '20_routines.sql', '30_views.sql'),
        'procedure': 'P_ACTIVITY_DAILY',
    },
}
