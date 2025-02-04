from behave import given, when, then
import os
import time
import uuid
import json
from datetime import datetime
from helpers import (
    template_helper,
    file_helper,
    aws_helper,
    file_comparer,
    kafka_data_generator,
    snapshot_data_generator,
    streaming_manifests_helper,
    streaming_data_helper,
    console_printer,
)

input_template = "current_valid_file_input.json"
output_template = "current_valid_file_output.json"


@given(
    "UCFS send '{record_count}' messages of type '{message_type}' with the given template files, encryption setting of '{encrypt_in_sender}' and wait setting of '{wait_for_sending}' with key method of '{key_method}'"
)
@given(
    "UCFS send '{record_count}' message of type '{message_type}' with the given template files, encryption setting of '{encrypt_in_sender}' and wait setting of '{wait_for_sending}' with key method of '{key_method}'"
)
def step_impl(
    context, record_count, message_type, encrypt_in_sender, wait_for_sending, key_method
):
    for row in context.table:
        context.execute_steps(
            f"given UCFS send '{record_count}' message of type '{message_type}' with input file of "
            + f"'{row['input-file-name-kafka']}', output file of '{row['output-file-name-kafka']}', "
            + f"dlq file of 'None', snapshot record file of '{row['snapshot-record-file-name-kafka']}', "
            + f"encryption setting of '{encrypt_in_sender}' and wait setting of '{wait_for_sending}' with key method of '{key_method}'"
        )


@given(
    "UCFS send '{record_count}' messages of type '{message_type}' with input file of '{input_file_name}', output file of '{output_file_name}', dlq file of '{dlq_file_name}', snapshot record file of '{snapshot_record_file_name}', encryption setting of '{encrypt_in_sender}' and wait setting of '{wait_for_sending}' with key method of '{key_method}'"
)
@given(
    "UCFS send '{record_count}' message of type '{message_type}' with input file of '{input_file_name}', output file of '{output_file_name}', dlq file of '{dlq_file_name}', snapshot record file of '{snapshot_record_file_name}', encryption setting of '{encrypt_in_sender}' and wait setting of '{wait_for_sending}' with key method of '{key_method}'"
)
def step_impl(
    context,
    record_count,
    message_type,
    input_file_name,
    output_file_name,
    dlq_file_name,
    snapshot_record_file_name,
    encrypt_in_sender,
    wait_for_sending,
    key_method,
):
    context.uploaded_id = uuid.uuid4()

    folder = streaming_data_helper.generate_fixture_data_folder(message_type)
    topic_prefix = streaming_data_helper.generate_topic_prefix(message_type)

    skip_encryption = "true" if encrypt_in_sender == "false" else "false"
    output_template = None if output_file_name == "None" else output_file_name
    dlq_template = None if dlq_file_name == "None" else dlq_file_name
    snapshot_record_file_name = (
        None if snapshot_record_file_name == "None" else snapshot_record_file_name
    )
    wait_for_sending_bool = wait_for_sending.lower() == "true"

    message_volume = (
        context.kafka_message_volume if context.kafka_message_volume else "1"
    )
    random_keys = context.kafka_random_key if context.kafka_random_key else "false"

    context.kafka_generated_dlq_output_files = []

    for topic in context.topics_for_test:
        key = None
        if key_method.lower() == "static":
            key = context.uploaded_id
        elif key_method.lower() == "topic":
            key = uuid.uuid4()

        topic_name = template_helper.get_topic_name(topic["topic"])

        generated_files = kafka_data_generator.generate_kafka_files(
            test_run_name=context.test_run_name,
            s3_input_bucket=context.s3_ingest_bucket,
            input_template_name=input_file_name,
            output_template_name=output_template,
            new_uuid=key,
            local_files_temp_folder=os.path.join(context.temp_folder, topic_name),
            fixture_files_root=context.fixture_path_local,
            s3_output_prefix=context.s3_temp_output_path,
            record_count=record_count,
            topic_name=topic["topic"],
            snapshots_output_folder=context.snapshot_files_hbase_records_temp_folder,
            seconds_timeout=context.timeout,
            fixture_data_folder=folder,
            dlq_template_name=dlq_template,
            snapshot_record_template_name=snapshot_record_file_name,
        )

        files_to_send_to_kafka_broker = [
            generated_file[0] for generated_file in generated_files
        ]
        aws_helper.send_files_to_kafka_producer_sns(
            dynamodb_table_name=context.dynamo_db_table_name,
            s3_input_bucket=context.s3_ingest_bucket,
            aws_acc_id=context.aws_acc,
            sns_topic_name=context.aws_sns_topic_name,
            fixture_files=files_to_send_to_kafka_broker,
            message_key=context.uploaded_id,
            topic_name=topic["topic"],
            topic_prefix=topic_prefix,
            region=context.aws_region_main,
            skip_encryption=skip_encryption,
            kafka_message_volume=message_volume,
            kafka_random_key=random_keys,
            wait_for_job_completion=wait_for_sending_bool,
        )

        dlq_files_for_topic = []
        for generated_file in generated_files:
            if len(generated_file) > 3:
                dlq_files_for_topic.append(generated_file[3])

        context.kafka_generated_dlq_output_files.append(
            (topic["topic"], dlq_files_for_topic)
        )


@when(
    "UCFS send the same message of type '{message_type}' via Kafka with a later timestamp"
)
def step_impl(context, message_type):
    context.execute_steps(
        f"when UCFS send a message of type '{message_type}' to each topic with date of '2019-11-01T03:02:01.001' and key of '{context.uploaded_id}'"
    )


@when(
    "UCFS send a message of type '{message_type}' to each topic with date of '{date}' and key of '{key}'"
)
def step_impl(context, message_type, date, key):
    folder = streaming_data_helper.generate_fixture_data_folder(message_type)
    topic_prefix = streaming_data_helper.generate_topic_prefix(message_type)

    qualified_key = None if key == "None" else key
    date_qualified = (
        None if date == "None" else datetime.strptime(date, "%Y-%m-%dT%H:%M:%S.%f")
    )
    for topic in context.topics_for_test:
        topic_name = template_helper.get_topic_name(topic["topic"])
        generated_files = kafka_data_generator.generate_kafka_files(
            test_run_name=context.test_run_name,
            s3_input_bucket=context.s3_ingest_bucket,
            input_template_name=input_template,
            output_template_name=output_template,
            new_uuid=qualified_key,
            local_files_temp_folder=os.path.join(context.temp_folder, topic_name),
            fixture_files_root=context.fixture_path_local,
            s3_output_prefix=context.s3_temp_output_path,
            record_count=1,
            topic_name=topic["topic"],
            snapshots_output_folder=context.snapshot_files_hbase_records_temp_folder,
            seconds_timeout=context.timeout,
            fixture_data_folder=folder,
            custom_base_timestamp=date_qualified,
        )

        files_to_send_to_kafka_broker = [
            generated_file[0] for generated_file in generated_files
        ]
        aws_helper.send_files_to_kafka_producer_sns(
            dynamodb_table_name=context.dynamo_db_table_name,
            s3_input_bucket=context.s3_ingest_bucket,
            aws_acc_id=context.aws_acc,
            sns_topic_name=context.aws_sns_topic_name,
            fixture_files=files_to_send_to_kafka_broker,
            message_key=key,
            topic_name=topic["topic"],
            topic_prefix=topic_prefix,
            region=context.aws_region_main,
        )


@then(
    "A single output message matching the Kafka dlq file '{dlq_file_template}' will be stored in the dlq S3 bucket folder"
)
def step_impl(context, dlq_file_template):
    for topic in context.topics_for_test:
        dlq_file = None
        for dlq_files_and_topic_tuple in context.kafka_generated_dlq_output_files:
            if topic["topic"] == dlq_files_and_topic_tuple[0]:
                for dlq_file_for_topic in dlq_files_and_topic_tuple[1]:
                    if dlq_file_template in dlq_file_for_topic:
                        dlq_file = dlq_file_for_topic

        if dlq_file is None:
            raise AssertionError(
                f"No generated dlq file could be found for dlq template of {dlq_file_template}"
            )

        expected_file_content = file_helper.get_contents_of_file(dlq_file, True)
        id_object = file_helper.get_id_object_from_json_file(dlq_file)

        dlq_full_file_path_s3 = os.path.join(
            context.s3_dlq_path_and_date_prefix, id_object
        )

        try:
            console_printer.print_info(
                f"Waiting for dlq file in s3 with prefix of '{dlq_full_file_path_s3}' in bucket '{context.s3_ingest_bucket}'"
            )
            aws_helper.wait_for_file_to_be_in_s3(
                context.s3_ingest_bucket, dlq_full_file_path_s3, context.timeout
            )
        except Exception as ex:
            raise AssertionError(ex)

        file_data = aws_helper.retrieve_files_from_s3(
            context.s3_ingest_bucket, dlq_full_file_path_s3
        )
        number_files = len(file_data)
        if number_files != 1:
            raise AssertionError(
                f"There should a single dlq file found for {dlq_full_file_path_s3} but was {number_files}"
            )

        input_json = json.loads(expected_file_content)
        output_json = json.loads(file_data[0])

        console_printer.print_info(
            f"Asserting unformatted dlq message actual '{input_json}' is like expected '{output_json}'"
        )

        assert input_json["key"] in output_json["body"]
        assert input_json["reason"] in output_json["reason"]

        input_json_formatted = file_helper.get_json_with_replaced_values(
            expected_file_content
        )
        output_json_formatted = file_helper.get_json_with_replaced_values(file_data[0])

        console_printer.print_info(
            f"Asserting formatted dlq message actual '{output_json_formatted}' is like expected '{input_json_formatted}'"
        )

        assert input_json_formatted == output_json_formatted


@then(
    "A message for the Kafka dlq file '{dlq_file_template}' will not be stored in HBase"
)
def step_impl(context, dlq_file_template):
    for topic in context.topics_for_test:
        dlq_file = None
        for dlq_files_and_topic_tuple in context.kafka_generated_dlq_output_files:
            if topic["topic"] == dlq_files_and_topic_tuple[0]:
                for dlq_file_for_topic in dlq_files_and_topic_tuple[1]:
                    if dlq_file_template in dlq_file_for_topic:
                        dlq_file = dlq_file_for_topic

        if dlq_file is None:
            raise AssertionError(
                f"No generated dlq file could be found for dlq template of {dlq_file_template}"
            )

        expected_file_content = file_helper.get_contents_of_file(dlq_file, True)
        id_object = file_helper.get_id_object_from_json_file(dlq_file)

        test_run_topic_name = template_helper.get_topic_name(topic["topic"])
        file_comparer.assert_specific_id_missing_in_hbase(
            test_run_topic_name, id_object, 5, True
        )


@when("The relevant formatted data is stored in HBase with id format of '{id_format}'")
@then("The relevant formatted data is stored in HBase with id format of '{id_format}'")
def step_impl(context, id_format):
    wrap_id_value = id_format == "wrapped"

    for result in file_comparer.assert_specific_file_stored_in_hbase_threaded(
        [topic["topic"] for topic in context.topics_for_test],
        context.importer_output_folder,
        context.timeout,
        record_expected_in_hbase=True,
        wrap_id=wrap_id_value,
    ):
        console_printer.print_info(
            f"Asserted hbase file present for topic with name of {result}"
        )


@when(
    "The relevant formatted data is not stored in HBase with id format of '{id_format}'"
)
@then(
    "The relevant formatted data is not stored in HBase with id format of '{id_format}'"
)
def step_impl(context, id_format):
    wrap_id_value = id_format == "wrapped"

    for result in file_comparer.assert_specific_file_stored_in_hbase_threaded(
        [topic["topic"] for topic in context.topics_for_test],
        context.importer_output_folder,
        60,
        record_expected_in_hbase=False,
        wrap_id=wrap_id_value,
    ):
        console_printer.print_info(
            f"Asserted hbase file present for topic with name of {result}"
        )


@given(
    "The latest timestamped '{message_type}' message has been stored in HBase unaltered with id format of '{id_format}'"
)
@when(
    "The latest timestamped '{message_type}' message has been stored in HBase unaltered with id format of '{id_format}'"
)
@then(
    "The latest timestamped '{message_type}' message has been stored in HBase unaltered with id format of '{id_format}'"
)
def step_impl(context, id_format, message_type):
    folder = streaming_data_helper.generate_fixture_data_folder(message_type)

    for topic in context.topics_for_test:
        topic_name = template_helper.get_topic_name(topic["topic"])
        temp_folder_for_topic = os.path.join(context.temp_folder, topic_name)
        full_folder_path = file_helper.generate_edited_files_folder(
            temp_folder_for_topic, folder
        )
        latest_file_path = file_helper.get_file_from_folder_with_latest_timestamp(
            full_folder_path
        )

        wrap_id_value = id_format == "wrapped"

        file_comparer.assert_specific_file_stored_in_hbase(
            topic_name,
            latest_file_path,
            context.timeout,
            record_expected_in_hbase=True,
            wrap_id=wrap_id_value,
        )


@given(
    "The latest timestamped '{message_type}' message has not been stored in HBase unaltered with id format of '{id_format}'"
)
@when(
    "The latest timestamped '{message_type}' message has not been stored in HBase unaltered with id format of '{id_format}'"
)
@then(
    "The latest timestamped '{message_type}' message has not been stored in HBase unaltered with id format of '{id_format}'"
)
def step_impl(context, id_format, message_type):
    folder = streaming_data_helper.generate_fixture_data_folder(message_type)

    for topic in context.topics_for_test:
        topic_name = template_helper.get_topic_name(topic["topic"])
        temp_folder_for_topic = os.path.join(context.temp_folder, topic_name)
        full_folder_path = file_helper.generate_edited_files_folder(
            temp_folder_for_topic, folder
        )
        latest_file_path = file_helper.get_file_from_folder_with_latest_timestamp(
            full_folder_path
        )

        wrap_id_value = id_format == "wrapped"

        file_comparer.assert_specific_file_stored_in_hbase(
            topic_name,
            latest_file_path,
            60,
            record_expected_in_hbase=False,
            wrap_id=wrap_id_value,
        )


@then(
    "The latest id and timestamp have been correctly logged to the streaming '{streaming_type}' manifests with id format of '{id_format}' for message type '{message_type}'"
)
def step_impl(context, streaming_type, id_format, message_type):
    folder = streaming_data_helper.generate_fixture_data_folder(message_type)

    manifest_bucket = context.manifest_s3_bucket

    valid_prefixes = {
        "main": context.k2hb_main_manifest_write_s3_prefix,
        "equalities": context.k2hb_equality_manifest_write_s3_prefix,
        "audit": context.k2hb_audit_manifest_write_s3_prefix,
    }
    manifest_base_prefix = valid_prefixes.get(streaming_type, "NOT_SET")

    if manifest_base_prefix == "NOT_SET":
        raise AssertionError(
            f"Could not find manifest prefix for streaming of '{streaming_type}'"
        )

    for topic in context.topics_for_test:
        topic_name = template_helper.get_topic_name(topic["topic"])
        temp_folder_for_topic = os.path.join(context.temp_folder, topic_name)
        full_folder_path = file_helper.generate_edited_files_folder(
            temp_folder_for_topic, folder
        )
        latest_file_path = file_helper.get_file_from_folder_with_latest_timestamp(
            full_folder_path
        )

        wrap_id_value = id_format == "wrapped"
        file_pattern = f"^.*_.*_\d+-.*_.*_\d+.txt$"

        console_printer.print_info(
            f"Looking for manifest files in '{manifest_bucket}' bucket with prefix of '{manifest_base_prefix}' and pattern of '{file_pattern}'"
        )

        manifest_files = aws_helper.retrieve_files_from_s3(
            manifest_bucket,
            manifest_base_prefix,
            file_pattern,
        )

        console_printer.print_info(f"Found '{len(manifest_files)}' manifest files")

        manifest_lines = []
        for manifest_file in manifest_files:
            manifest_lines_in_file = manifest_file.splitlines()
            manifest_lines.extend(
                [
                    manifest_line_in_file.replace('""', '"')
                    for manifest_line_in_file in manifest_lines_in_file
                ]
            )

        record_id = file_helper.get_id_object_from_json_file(latest_file_path)
        record_timestamp = file_helper.get_timestamp_as_long_from_json_file(
            latest_file_path
        )

        expected = streaming_manifests_helper.generate_correct_manifest_line(
            record_id, record_timestamp, topic_name, wrap_id=wrap_id_value
        )

        console_printer.print_info(f"Expecting manifest line with data of '{expected}'")
        console_printer.print_info(f"Actual manifest lines were '{manifest_lines}'")

        assert expected in manifest_lines
