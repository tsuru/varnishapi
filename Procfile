web: gunicorn feaas.api:api -b 0.0.0.0:$PORT
vcl_writer: python run_vcl_writer.py $VCL_WRITER_ARGS
instance_starter: python run_instance_starter.py $INSTANCE_STARTER_ARGS
