<?php
/**
 * Plugin Name: Pupas Migration Auth
 * Description: Valida una sola vez las credenciales de clientes migrados.
 * Version: 1.0.0
 */
if (!defined('ABSPATH')) exit;
add_action('rest_api_init', function () {
    register_rest_route('pupas-migration/v1', '/verify', [
        'methods' => 'POST',
        'permission_callback' => '__return_true',
        'callback' => function (WP_REST_Request $request) {
            $configured = defined('PUPAS_MIGRATION_SECRET') ? PUPAS_MIGRATION_SECRET : '';
            $provided = $request->get_header('X-Pupas-Migration-Secret');
            if (!$configured || !$provided || !hash_equals($configured, $provided))
                return new WP_Error('forbidden', 'Acceso denegado.', ['status' => 403]);
            $email = sanitize_email($request->get_param('email'));
            $password = (string) $request->get_param('password');
            $account = get_user_by('email', $email);
            if (!$account || is_wp_error(wp_authenticate($account->user_login, $password)))
                return new WP_Error('invalid_credentials', 'Credenciales inválidas.', ['status' => 401]);
            return ['valid' => true];
        },
    ]);
});
