// Smart Notes Extension Debug Helper
// Run this in the browser console to debug extension issues

(function() {
  console.log('🔍 Smart Notes Extension Debug Tool');
  console.log('=====================================');
  
  // Check if content script is loaded
  const contentScriptLoaded = typeof window.selectedText !== 'undefined';
  console.log('✓ Content script loaded:', contentScriptLoaded);
  
  // Check if CSS is injected
  const cssInjected = document.querySelector('style') && 
    Array.from(document.querySelectorAll('style')).some(style => 
      style.textContent.includes('smart-notes-overlay')
    );
  console.log('✓ CSS injected:', cssInjected);
  
  // Check for CSP issues
  const metaCSP = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
  if (metaCSP) {
    console.log('⚠ CSP detected:', metaCSP.content);
  } else {
    console.log('✓ No meta CSP detected');
  }
  
  // Test text selection
  console.log('📝 Testing text selection...');
  console.log('   Current selection:', window.getSelection().toString());
  
  // Check extension context menu
  console.log('🖱 To test context menu: Select text and right-click');
  
  // Test modal creation
  console.log('🪟 Testing modal creation...');
  
  function testModal() {
    try {
      const testData = {
        text: 'Test text for debugging',
        url: window.location.href,
        title: document.title
      };
      
      // Try to trigger the modal (if content script is available)
      if (typeof showCaptureModal === 'function') {
        showCaptureModal(testData);
        console.log('✓ Modal test successful');
      } else {
        console.log('✗ showCaptureModal function not available');
        
        // Fallback: send message to background
        if (chrome && chrome.runtime) {
          chrome.runtime.sendMessage({
            action: 'showModal',
            data: testData
          }, (response) => {
            console.log('Background response:', response);
          });
        }
      }
    } catch (error) {
      console.log('✗ Modal test failed:', error);
    }
  }
  
  // Add test button to page
  const testBtn = document.createElement('button');
  testBtn.textContent = '🧪 Test Smart Notes Modal';
  testBtn.style.cssText = `
    position: fixed;
    top: 10px;
    left: 10px;
    z-index: 999999;
    background: #007bff;
    color: white;
    border: none;
    padding: 10px;
    border-radius: 5px;
    cursor: pointer;
    font-family: monospace;
    font-size: 12px;
  `;
  testBtn.onclick = testModal;
  
  if (document.body) {
    document.body.appendChild(testBtn);
    console.log('✓ Test button added to page');
  }
  
  // Show final status
  console.log('=====================================');
  console.log('🏁 Debug complete. Check console output above.');
  console.log('   Use the blue test button to trigger modal');
  console.log('   Or select text and right-click for normal flow');
  
})();
