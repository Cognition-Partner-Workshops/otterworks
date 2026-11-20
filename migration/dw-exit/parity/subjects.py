"""Subject-area execution contracts for local relational parity."""

SUBJECTS = {
    'users': {
        'stages': ('10_load.sql', '20_routines.sql', '30_views.sql'),
        'procedure': 'P_ACTIVITY_DAILY',
    },
}
