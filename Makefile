KUBECMD := ~/kubectl

start-basic:
	$(KUBECMD) apply -f batchgeocode.yaml
    
stop-basic:
	$(KUBECMD) delete -f batchgeocode.yaml

reset-basic: stop-basic start-basic

status:
	$(KUBECMD) get pods --namespace batch-geocode

get_ip:
	$(KUBECMD) get services --namespace batch-geocode