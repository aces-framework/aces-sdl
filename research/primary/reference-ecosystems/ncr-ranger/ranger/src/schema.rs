// @generated automatically by Diesel CLI.

diesel::table! {
    accounts (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        template_id -> Binary,
        username -> Tinytext,
        password -> Nullable<Tinytext>,
        private_key -> Nullable<Text>,
        #[max_length = 16]
        exercise_id -> Binary,
        created_at -> Timestamp,
        updated_at -> Timestamp,
        deleted_at -> Timestamp,
    }
}

diesel::table! {
    artifacts (id) {
        #[max_length = 16]
        id -> Binary,
        name -> Tinytext,
        content -> Mediumblob,
        #[max_length = 16]
        metric_id -> Binary,
        created_at -> Timestamp,
        updated_at -> Timestamp,
        deleted_at -> Timestamp,
    }
}

diesel::table! {
    banners (exercise_id) {
        #[max_length = 16]
        exercise_id -> Binary,
        name -> Tinytext,
        content -> Mediumblob,
        created_at -> Timestamp,
        updated_at -> Timestamp,
    }
}

diesel::table! {
    condition_messages (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        exercise_id -> Binary,
        #[max_length = 16]
        deployment_id -> Binary,
        #[max_length = 16]
        virtual_machine_id -> Binary,
        condition_name -> Tinytext,
        #[max_length = 16]
        condition_id -> Binary,
        value -> Decimal,
        created_at -> Timestamp,
        deleted_at -> Timestamp,
    }
}

diesel::table! {
    custom_elements (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        order_id -> Binary,
        name -> Tinytext,
        description -> Text,
        #[max_length = 16]
        environment_id -> Binary,
    }
}

diesel::table! {
    deployment_elements (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        deployment_id -> Binary,
        scenario_reference -> Tinytext,
        handler_reference -> Nullable<Tinytext>,
        deployer_type -> Tinytext,
        status -> Tinytext,
        executor_stdout -> Nullable<Mediumtext>,
        executor_stderr -> Nullable<Mediumtext>,
        #[max_length = 16]
        event_id -> Nullable<Binary>,
        #[max_length = 16]
        parent_node_id -> Nullable<Binary>,
        error_message -> Nullable<Text>,
        created_at -> Timestamp,
        deleted_at -> Timestamp,
    }
}

diesel::table! {
    deployments (id) {
        #[max_length = 16]
        id -> Binary,
        name -> Tinytext,
        group_name -> Nullable<Tinytext>,
        deployment_group -> Tinytext,
        sdl_schema -> Longtext,
        #[max_length = 16]
        exercise_id -> Binary,
        created_at -> Timestamp,
        updated_at -> Timestamp,
        deleted_at -> Timestamp,
        start -> Timestamp,
        end -> Timestamp,
    }
}

diesel::table! {
    email_statuses (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        email_id -> Binary,
        name -> Tinytext,
        message -> Nullable<Text>,
        created_at -> Timestamp,
    }
}

diesel::table! {
    email_templates (id) {
        #[max_length = 16]
        id -> Binary,
        name -> Tinytext,
        content -> Text,
        created_at -> Timestamp,
    }
}

diesel::table! {
    emails (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        exercise_id -> Binary,
        user_id -> Nullable<Text>,
        from_address -> Text,
        to_addresses -> Text,
        reply_to_addresses -> Nullable<Text>,
        cc_addresses -> Nullable<Text>,
        bcc_addresses -> Nullable<Text>,
        subject -> Text,
        body -> Text,
        created_at -> Timestamp,
    }
}

diesel::table! {
    environment_strength (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        environment_id -> Binary,
        strength -> Tinytext,
    }
}

diesel::table! {
    environment_weakness (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        environment_id -> Binary,
        weakness -> Tinytext,
    }
}

diesel::table! {
    environments (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        order_id -> Binary,
        name -> Tinytext,
        category -> Tinytext,
        size -> Integer,
        additional_information -> Nullable<Longtext>,
    }
}

diesel::table! {
    event_info_data (checksum) {
        #[max_length = 64]
        checksum -> Char,
        name -> Tinytext,
        file_name -> Tinytext,
        file_size -> Unsigned<Bigint>,
        content -> Mediumblob,
        created_at -> Timestamp,
    }
}

diesel::table! {
    events (id) {
        #[max_length = 16]
        id -> Binary,
        name -> Tinytext,
        start -> Timestamp,
        end -> Timestamp,
        #[max_length = 16]
        deployment_id -> Binary,
        description -> Nullable<Mediumtext>,
        has_triggered -> Bool,
        triggered_at -> Timestamp,
        #[max_length = 64]
        event_info_data_checksum -> Nullable<Char>,
        created_at -> Timestamp,
        updated_at -> Timestamp,
        deleted_at -> Timestamp,
    }
}

diesel::table! {
    exercises (id) {
        #[max_length = 16]
        id -> Binary,
        name -> Tinytext,
        group_name -> Nullable<Tinytext>,
        deployment_group -> Tinytext,
        sdl_schema -> Nullable<Longtext>,
        created_at -> Timestamp,
        updated_at -> Timestamp,
        deleted_at -> Timestamp,
    }
}

diesel::table! {
    metrics (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        exercise_id -> Binary,
        #[max_length = 16]
        deployment_id -> Binary,
        entity_selector -> Text,
        name -> Nullable<Text>,
        sdl_key -> Text,
        description -> Nullable<Text>,
        role -> Tinytext,
        text_submission -> Nullable<Text>,
        score -> Nullable<Unsigned<Integer>>,
        max_score -> Unsigned<Integer>,
        has_artifact -> Bool,
        created_at -> Timestamp,
        updated_at -> Timestamp,
        deleted_at -> Timestamp,
    }
}

diesel::table! {
    orders (id) {
        #[max_length = 16]
        id -> Binary,
        name -> Tinytext,
        client_id -> Text,
        created_at -> Timestamp,
        updated_at -> Timestamp,
        deleted_at -> Timestamp,
        status -> Tinytext,
    }
}

diesel::table! {
    participants (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        deployment_id -> Binary,
        user_id -> Text,
        selector -> Text,
        created_at -> Timestamp,
        updated_at -> Timestamp,
        deleted_at -> Timestamp,
    }
}

diesel::table! {
    plot_point_structures (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        plot_point_id -> Binary,
        #[max_length = 16]
        structure_id -> Binary,
    }
}

diesel::table! {
    plot_points (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        plot_id -> Binary,
        #[max_length = 16]
        objective_id -> Binary,
        name -> Tinytext,
        description -> Text,
        trigger_time -> Timestamp,
    }
}

diesel::table! {
    plots (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        order_id -> Binary,
        name -> Tinytext,
        description -> Text,
        start_time -> Timestamp,
        end_time -> Timestamp,
    }
}

diesel::table! {
    skills (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        structure_id -> Binary,
        skill -> Tinytext,
    }
}

diesel::table! {
    structure_training_objectives (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        structure_id -> Binary,
        #[max_length = 16]
        training_objective_id -> Binary,
    }
}

diesel::table! {
    structure_weaknesses (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        structure_id -> Binary,
        weakness -> Tinytext,
    }
}

diesel::table! {
    structures (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        order_id -> Binary,
        #[max_length = 16]
        parent_id -> Nullable<Binary>,
        name -> Tinytext,
        description -> Nullable<Text>,
    }
}

diesel::table! {
    threats (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        training_objective_id -> Binary,
        threat -> Tinytext,
    }
}

diesel::table! {
    training_objectives (id) {
        #[max_length = 16]
        id -> Binary,
        #[max_length = 16]
        order_id -> Binary,
        objective -> Tinytext,
    }
}

diesel::joinable!(accounts -> exercises (exercise_id));
diesel::joinable!(banners -> exercises (exercise_id));
diesel::joinable!(condition_messages -> deployments (deployment_id));
diesel::joinable!(custom_elements -> orders (order_id));
diesel::joinable!(deployment_elements -> deployments (deployment_id));
diesel::joinable!(deployment_elements -> events (event_id));
diesel::joinable!(deployments -> exercises (exercise_id));
diesel::joinable!(email_statuses -> emails (email_id));
diesel::joinable!(emails -> exercises (exercise_id));
diesel::joinable!(environment_strength -> environments (environment_id));
diesel::joinable!(environment_weakness -> environments (environment_id));
diesel::joinable!(environments -> orders (order_id));
diesel::joinable!(metrics -> deployments (deployment_id));
diesel::joinable!(participants -> deployments (deployment_id));
diesel::joinable!(plot_point_structures -> plot_points (plot_point_id));
diesel::joinable!(plot_point_structures -> structures (structure_id));
diesel::joinable!(plot_points -> plots (plot_id));
diesel::joinable!(plots -> orders (order_id));
diesel::joinable!(skills -> structures (structure_id));
diesel::joinable!(structure_training_objectives -> structures (structure_id));
diesel::joinable!(structure_training_objectives -> training_objectives (training_objective_id));
diesel::joinable!(structure_weaknesses -> structures (structure_id));
diesel::joinable!(structures -> orders (order_id));
diesel::joinable!(threats -> training_objectives (training_objective_id));
diesel::joinable!(training_objectives -> orders (order_id));

diesel::allow_tables_to_appear_in_same_query!(
    accounts,
    artifacts,
    banners,
    condition_messages,
    custom_elements,
    deployment_elements,
    deployments,
    email_statuses,
    email_templates,
    emails,
    environment_strength,
    environment_weakness,
    environments,
    event_info_data,
    events,
    exercises,
    metrics,
    orders,
    participants,
    plot_point_structures,
    plot_points,
    plots,
    skills,
    structure_training_objectives,
    structure_weaknesses,
    structures,
    threats,
    training_objectives,
);
