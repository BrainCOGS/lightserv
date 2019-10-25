$(function() {

	// jQuery selection for the 2 select boxes
	var dropdown = {
		center: $('#select_center'),
		microscope: $('#select_microscope')
	};
	// console.log(dropdown)
	// dropdown.state.empty();
	// dropdown.county.empty();
	// call to update on load
	updateMicroscopes();

	// function to call XHR and update county dropdown
	function updateMicroscopes() {
		var send = {
			center: dropdown.center.val()
		};
		// console.log(send)
		dropdown.microscope.attr('disabled', 'disabled');
		dropdown.microscope.empty();
		$.getJSON("{{ url_for('microscope._get_microscopes') }}", send, function(data) {
			data.forEach(function(item) {
				dropdown.microscope.append(
					$('<option>', {
						value: item[0],
						text: item[1]
					})
				);
			});
			dropdown.microscope.removeAttr('disabled');
		});
	}

	// event listener to state dropdown change
	dropdown.center.on('change', function() {
		updateMicroscopes();
	});

});